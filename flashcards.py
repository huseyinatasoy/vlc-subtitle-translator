"""Kart oyunu: kelime ön yüzde, tıklayınca çevirisi. Puan yok; kullanıcı kendini dener."""
import random
import tkinter as tk
from tkinter import ttk

import theme
from i18n import _
from theme import CARD2, COLORS, FAV, FONT, LABELS, MUTED
from translator import TranslateError, translate_word

ACCENT = theme.ACCENT_HI


class FlashcardWindow:
    DECKS = [('learn', _('Bilmiyorum + Öğreniyorum')), ('red', _('●  Bilmiyorum')),
             ('yellow', _('●  Öğreniyorum')), ('fav', _('★  Favoriler')), ('all', _('Tüm kelimeler'))]

    def __init__(self, app):
        self.app = app
        self.deck = []
        self.pos = 0
        self.flipped = False
        self.errors = {}   # kelime -> çeviri hatası metni
        self.loading = set()
        ui = app.ui
        win = self.win = tk.Toplevel(app.root)
        win.title(_('Kart oyunu'))
        win.resizable(False, False)
        theme.window(win)

        top = ttk.Frame(win, padding=(16, 14, 16, 10))
        top.pack(fill='x')
        ttk.Label(top, text=_('Kart oyunu'), style='Title.TLabel').pack(side='left', padx=(0, 18))
        self.deck_var = tk.StringVar(value=self.DECKS[0][1])
        cb = ttk.Combobox(top, textvariable=self.deck_var, state='readonly', width=24,
                          values=[name for key, name in self.DECKS])
        cb.pack(side='left')
        cb.bind('<<ComboboxSelected>>', lambda e: self.build(shuffle=True))
        self.count_var = tk.StringVar()
        ttk.Label(top, textvariable=self.count_var, style='Muted.TLabel').pack(side='right')

        mid = ttk.Frame(win, padding=(16, 0))
        mid.pack()
        self.card = tk.Frame(mid, bg=CARD2, width=int(540 * ui), height=int(290 * ui), cursor='hand2')
        self.card.pack_propagate(False)
        self.card.pack()

        bot = ttk.Frame(win, padding=16)
        bot.pack(fill='x')
        ttk.Button(bot, text=_('‹  Önceki'), command=lambda: self.move(-1)).pack(side='left')
        ttk.Button(bot, text=_('Karıştır'), command=lambda: self.build(shuffle=True)).pack(side='left', padx=8)
        ttk.Button(bot, text=_('Sonraki  ›'), style='Accent.TButton',
                   command=lambda: self.move(1)).pack(side='right')
        ttk.Label(win, text=_('Kartı çevirmek için tıkla ya da Boşluk · ← → ile gez'),
                  style='Muted.TLabel').pack(pady=(0, 12))

        for seq in ('<space>', '<Return>'):
            win.bind(seq, lambda e: self.flip())
        win.bind('<Left>', lambda e: self.move(-1))
        win.bind('<Right>', lambda e: self.move(1))
        app.store.listeners.append(self._on_store)
        win.protocol('WM_DELETE_WINDOW', self.close)
        self.build(shuffle=True)
        win.focus_force()

    def close(self):
        if self._on_store in self.app.store.listeners:
            self.app.store.listeners.remove(self._on_store)
        self.app.flashcards_window = None
        self.win.destroy()

    # -- deste ---------------------------------------------------------
    def _deck_key(self):
        name = self.deck_var.get()
        return next(k for k, n in self.DECKS if n == name)

    def _words(self):
        k = self._deck_key()
        for w, e in self.app.store.words.items():
            c = e.get('color')
            if (k == 'learn' and c in ('red', 'yellow')) or k == c or (k == 'fav' and e.get('fav')) \
                    or k == 'all':
                yield w

    def build(self, shuffle=False):
        current = self.deck[self.pos] if self.deck else None
        words = list(self._words())
        if shuffle:
            random.shuffle(words)
            self.pos = 0
        else:
            # mevcut sırayı koru: silinenleri at, yenileri sona ekle
            keep = [w for w in self.deck if w in words]
            words = keep + [w for w in words if w not in keep]
            self.pos = words.index(current) if current in words else min(self.pos, max(0, len(words) - 1))
        self.deck = words
        if shuffle or not words or words[self.pos] != current:
            self.flipped = False
        self.render()

    def _on_store(self):
        if self.win.winfo_exists():
            self.build()

    def move(self, step):
        if not self.deck:
            return
        self.pos = (self.pos + step) % len(self.deck)
        self.flipped = False
        self.render()

    def flip(self):
        if not self.deck:
            return
        self.flipped = not self.flipped
        if self.flipped:
            self._ensure_translation(self.deck[self.pos])
        self.render()

    # -- çeviri --------------------------------------------------------
    def _translation(self, w):
        entry = self.app.store.get(w) or {}
        if entry.get('tr'):
            return entry['tr']
        info = self.app.tcache.get(self.app.lang_pair(), w)
        return info.get('main') if info else None

    def _ensure_translation(self, w):
        if self._translation(w) or w in self.loading:
            return
        self.loading.add(w)
        self.errors.pop(w, None)
        pair, opts = self.app.lang_pair(), self.app.translate_opts()

        def done(res, err):
            self.loading.discard(w)
            if err is None:
                self.app.tcache.put(pair, w, res)
                if self.app.store.get(w) is not None:
                    self.app.store.set_translation(w, res['main'])  # listener render eder
            else:
                self.errors[w] = str(err) if isinstance(err, TranslateError) else _('internet bağlantısı?')
            if self.win.winfo_exists():
                self.render()
        self.app.run_bg(lambda: translate_word(w, *opts), done)

    # -- çizim ---------------------------------------------------------
    def render(self):
        card = self.card
        for child in card.winfo_children():
            child.destroy()
        total = len(self.deck)
        self.count_var.set('%d / %d' % (self.pos + 1, total) if total else '')
        if not total:
            card.configure(cursor='arrow')
            tk.Label(card, text=_('Bu grupta kelime yok.\nAltyazıda kelimelerin üzerine gelip renklendir.'),
                     fg=MUTED, bg=CARD2, font=(FONT, 12), justify='center').place(relx=.5, rely=.5, anchor='center')
            return
        card.configure(cursor='hand2')
        w = self.deck[self.pos]
        entry = self.app.store.get(w) or {}
        color = COLORS.get(entry.get('color'))

        tag = tk.Frame(card, bg=CARD2)
        tag.place(x=16, y=12)
        if color:
            tk.Label(tag, text='● ' + LABELS[entry['color']], fg=color, bg=CARD2,
                     font=(FONT, 9, 'bold')).pack(side='left')
        if entry.get('fav'):
            tk.Label(tag, text='  ★', fg=FAV, bg=CARD2, font=(FONT, 10)).pack(side='left')

        body = tk.Frame(card, bg=CARD2)
        body.place(relx=.5, rely=.5, anchor='center')
        wrap = int(480 * self.app.ui)
        if not self.flipped:
            tk.Label(body, text=w, fg='#ffffff', bg=CARD2, font=(FONT, 30, 'bold'),
                     wraplength=wrap).pack()
            tk.Label(body, text=_('çevirmek için tıkla'), fg=MUTED, bg=CARD2,
                     font=(FONT, 9)).pack(pady=(10, 0))
        else:
            tk.Label(body, text=w, fg=MUTED, bg=CARD2, font=(FONT, 12)).pack()
            tr = self._translation(w)
            if tr:
                tk.Label(body, text=tr, fg=ACCENT, bg=CARD2, font=(FONT, 26, 'bold'),
                         wraplength=wrap, justify='center').pack(pady=(6, 0))
            elif w in self.errors:
                tk.Label(body, text=_('Çeviri alınamadı: %s') % self.errors[w], fg=theme.ERR, bg=CARD2,
                         font=(FONT, 11), wraplength=wrap, justify='center').pack(pady=(6, 0))
            else:
                tk.Label(body, text=_('çevriliyor…'), fg=MUTED, bg=CARD2,
                         font=(FONT, 12, 'italic')).pack(pady=(6, 0))
            if entry.get('example'):
                tk.Label(body, text='“%s”' % entry['example'], fg=MUTED, bg=CARD2,
                         font=(FONT, 10, 'italic'), wraplength=wrap, justify='center').pack(pady=(14, 0))

        for widget in (card, tag, body, *tag.winfo_children(), *body.winfo_children()):
            widget.bind('<Button-1>', lambda e: self.flip())
