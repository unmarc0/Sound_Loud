"""
Sound Loud Pro – reproductor MP3 + descargador YouTube
"""

# ─── imports y constantes ──────────────────────────────────────────
import os, threading, time, tkinter as tk
from dataclasses import dataclass, field
from typing import List, Tuple
from tkinter import ttk
from PIL import Image, ImageTk
from pygame import mixer
from mutagen.mp3 import MP3
import yt_dlp

BG_MAIN="#121212"; BG_PANEL="#1E1E1E"; ACCENT="#ff6f00"; ACC_HOV="#ff8c1a"; TXT="#F0F0F0"
FONT=("Segoe UI",10); FBOLD=("Segoe UI Semibold",10)

# ─── backend util (búsqueda / descarga) ────────────────────────────
def yt_search(q:str)->List[Tuple[str,str]]:
    with yt_dlp.YoutubeDL({"quiet":True,"extract_flat":True,"skip_download":True}) as y:
        d=y.extract_info(f"ytsearch15:{q}",download=False)
    return [(e["title"],e["url"]) for e in d["entries"]]

def yt_download(title,url):
    os.makedirs("library",exist_ok=True); mp3=f"{title}.mp3"
    opts={"format":"bestaudio/best","outtmpl":f"library/{mp3}","quiet":True,
          "postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]}
    with yt_dlp.YoutubeDL(opts) as y: y.download([url]); return mp3

for d in("library","playlists"): os.makedirs(d,exist_ok=True)
def lib_tracks(): return [f for f in os.listdir("library") if f.endswith(".mp3")]
def playlists():  return [f[:-4] for f in os.listdir("playlists") if f.endswith(".txt")]
def pl_tracks(n): p=f"playlists/{n}.txt"; return open(p,encoding="utf-8").read().splitlines() if os.path.exists(p) else []

@dataclass
class State:
    tracks: List[str] = field(default_factory=lib_tracks)
    idx:    int       = 0

# ─── clase UI ──────────────────────────────────────────────────────
class SoundLoud:
    def __init__(s, root: tk.Tk):
        mixer.init()
        s.r=root; root.title("Sound Loud"); root.configure(bg=BG_MAIN)
        s.state=State(); s.playing=False; s.start=s.pause_off=s.len=0
        s.current_pl=None; s.tracks_vis=s.add_vis=s.newpl_vis=False
        s.pending_song=None                         # canción retenida

        st=ttk.Style(); st.theme_use("clam")
        st.configure("TNotebook",background=BG_MAIN,borderwidth=0)
        st.configure("TNotebook.Tab",background=BG_MAIN,foreground=ACCENT,font=FBOLD,padding=(14,6))
        st.map("TNotebook.Tab",background=[("selected",ACCENT)],foreground=[("selected",BG_MAIN)])
        st.configure("Accent.TButton",background=ACCENT,foreground=BG_MAIN,font=FBOLD,relief="flat",padding=6)
        st.map("Accent.TButton",background=[("active",ACC_HOV)])
        st.configure("Flat.TButton",background=BG_PANEL,foreground=TXT,font=FONT,relief="flat",padding=4)
        st.map("Flat.TButton",background=[("active","#2a2a2a")])
        st.configure("TScale",troughcolor="#333",sliderlength=12)

        s.nb=ttk.Notebook(root)
        s.tab_s=tk.Frame(s.nb,bg=BG_MAIN); s.tab_l=tk.Frame(s.nb,bg=BG_MAIN); s.tab_p=tk.Frame(s.nb,bg=BG_MAIN)
        for t,name in((s.tab_s,"Buscar"),(s.tab_l,"Librería"),(s.tab_p,"Listas")): s.nb.add(t,text=name)
        s.nb.pack(expand=True,fill="both")

        s.info=tk.Label(root,text="",fg=ACCENT,bg=BG_MAIN,font=FBOLD); s.info.pack(pady=4)

        s._build_search(); s._build_library(); s._build_playlists(); s._refresh_library()

    # ─── pestaña SEARCH ────────────────────────────────────────────
    def _build_search(s):
        s.q=tk.Entry(s.tab_s,bg=BG_PANEL,fg=TXT,insertbackground=TXT,relief="flat",font=FONT)
        s.q.pack(fill="x",padx=16,pady=(18,6))
        ttk.Button(s.tab_s,text="Buscar",style="Accent.TButton",command=s._search).pack(pady=(0,8))
        s.res=tk.Listbox(s.tab_s,bg=BG_PANEL,fg=TXT,selectbackground=ACCENT,font=FONT,bd=0,highlightthickness=0)
        s.res.pack(fill="both",expand=True,padx=16,pady=6); s.res.bind("<Double-1>",s._download_confirm)

    # ─── pestaña LIBRERÍA (► cambios en slider) ────────────────────
    def _build_library(s):
        s.lib=tk.Listbox(s.tab_l,bg=BG_PANEL,fg=TXT,selectbackground=ACCENT,font=FONT,bd=0,highlightthickness=0)
        s.lib.pack(fill="both",expand=True,padx=16,pady=8); s.lib.bind("<Double-1>",lambda _e:s._delete_song())

        ctrl=tk.Frame(s.tab_l,bg=BG_MAIN); ctrl.pack(pady=6)
        for ico,cmd in("⏮",s.prev),("▶",s.play_pause),("⏭",s.next):
            ttk.Button(ctrl,text=ico,width=3,style="Accent.TButton",command=cmd).pack(side="left",padx=3)
        s.pp_lib=ctrl.winfo_children()[1]

        # ► Slider ahora solo hace preview; commit en mouse release
        s.seek=ttk.Scale(s.tab_l,from_=0,to=100,orient="horizontal",length=460,command=s._seek_preview)
        s.seek.pack(pady=4)
        s.seek.bind("<ButtonRelease-1>",s._seek_commit)

        s.time=tk.Label(s.tab_l,text="00:00 / 00:00",fg=TXT,bg=BG_MAIN,font=FONT); s.time.pack()

        vol=ttk.Scale(s.tab_l,from_=0,to=1,orient="horizontal",length=180,command=lambda v:mixer.music.set_volume(float(v)))
        vol.set(0.5); vol.pack(pady=(12,6)); tk.Label(s.tab_l,text="Volumen",fg=TXT,bg=BG_MAIN,font=FONT).pack()

        ttk.Button(s.tab_l,text="➕ Añadir a Lista",style="Flat.TButton",command=s._add_toggle).pack(pady=(8,6))

        # panel inline añadir
        s.add_frame=tk.Frame(s.tab_l,bg=BG_PANEL,bd=1,relief="groove")
        tk.Label(s.add_frame,text="Elegir lista destino:",fg=TXT,bg=BG_PANEL,font=FBOLD).pack(pady=(6,4))
        s.add_box=tk.Listbox(s.add_frame,bg="#252525",fg=TXT,selectbackground=ACCENT,font=FONT,bd=0,highlightthickness=0,height=5,width=24)
        s.add_box.pack(padx=12,pady=4)
        r=tk.Frame(s.add_frame,bg=BG_PANEL); r.pack(pady=(4,8))
        ttk.Button(r,text="Añadir",style="Accent.TButton",command=s._add_confirm).pack(side="left",padx=4)
        ttk.Button(r,text="Cancelar",style="Flat.TButton",command=s._add_toggle).pack(side="left",padx=4)

    # ─── pestaña PLAYLISTS ─────────────────────────────────────────
    def _build_playlists(s):
        s.pl=tk.Listbox(s.tab_p,bg=BG_PANEL,fg=TXT,selectbackground=ACCENT,font=FONT,bd=0,highlightthickness=0)
        s.pl.pack(fill="both",expand=True,padx=16,pady=8)
        c1=tk.Frame(s.tab_p,bg=BG_MAIN); c1.pack(pady=6)
        for ico,cmd in("⏮",s.prev),("▶",s._pl_play_toggle),("⏭",s.next):
            ttk.Button(c1,text=ico,width=3,style="Accent.TButton",command=cmd).pack(side="left",padx=3)
        s.pp_pl=c1.winfo_children()[1]

        c2=tk.Frame(s.tab_p,bg=BG_MAIN); c2.pack(pady=(0,10))
        ttk.Button(c2,text="➕ Nueva",style="Flat.TButton",command=s._newpl_toggle).pack(side="left",padx=4)
        ttk.Button(c2,text="🗑 Borrar",style="Flat.TButton",command=s._pl_delete).pack(side="left",padx=4)
        s.view_btn=ttk.Button(c2,text="👁 Ver",style="Flat.TButton",command=s._tracks_toggle); s.view_btn.pack(side="left",padx=4)

        # panel inline crear playlist
        s.newpl_frame=tk.Frame(s.tab_p,bg=BG_PANEL,bd=1,relief="groove")
        tk.Label(s.newpl_frame,text="Nombre lista:",fg=TXT,bg=BG_PANEL,font=FBOLD).pack(pady=(6,4))
        s.newpl_entry=tk.Entry(s.newpl_frame,bg="#252525",fg=TXT,insertbackground=TXT,relief="flat",font=FONT)
        s.newpl_entry.pack(padx=12,fill="x")
        r=tk.Frame(s.newpl_frame,bg=BG_PANEL); r.pack(pady=(4,8))
        ttk.Button(r,text="Crear",style="Accent.TButton",command=s._newpl_confirm).pack(side="left",padx=4)
        ttk.Button(r,text="Cancelar",style="Flat.TButton",command=s._newpl_toggle).pack(side="left",padx=4)

        s.tracks=tk.Listbox(s.tab_p,bg=BG_PANEL,fg=TXT,selectbackground=ACCENT,font=FONT,bd=0,highlightthickness=0)
    # ─── lógica SEARCH ─────────────────────────────────────────────
    def _search(s):
        q=s.q.get().strip()
        if not q: return
        try:
            res=yt_search(q); s.video={}
            s.res.delete(0,tk.END)
            for t,u in res: s.res.insert(tk.END,t); s.video[t]=u
            s.info.config(text="Doble‑clic para descargar…")
        except Exception as e:
            s.info.config(text=f"Error: {e}")

    def _download_confirm(s,_):
        sel=s.res.curselection()
        if not sel: return
        t=s.res.get(sel[0]); url=s.video[t]
        s.info.config(text=f"Descargando '{t}'…")
        threading.Thread(target=s._dl_thread,args=(t,url),daemon=True).start()

    def _dl_thread(s,title,url):
        try:
            f=yt_download(title,url); s.state.tracks.append(f)
            s._refresh_library(); s.info.config(text=f"✓ '{title}' listo")
        except Exception as e: s.info.config(text=f"Error: {e}")

    # ─── helpers LIBRERÍA ─────────────────────────────────────────
    def _refresh_library(s,tracks=None):
        s.lib.delete(0,tk.END)
        s.state.tracks=tracks or lib_tracks()
        for t in s.state.tracks: s.lib.insert(tk.END,t)

    def _sync_icons(s):
        ico="⏸" if s.playing else "▶"
        s.pp_lib.config(text=ico); s.pp_pl.config(text=ico)

    def play_pause(s):
        if not s.state.tracks: return
        if mixer.music.get_busy() and s.playing:
            s.pause_off=time.time()-s.start; mixer.music.pause(); s.playing=False
        else:
            if not mixer.music.get_busy():
                s.state.idx=s.lib.curselection()[0] if s.lib.curselection() else 0
            tr=os.path.join("library",s.state.tracks[s.state.idx])
            mixer.music.load(tr); mixer.music.play(start=s.pause_off)
            s.start=time.time()-s.pause_off; s.playing=True
            s._set_length(tr); s._loop(); s._watch_end()
        s._sync_icons()

    def _set_length(s,fp):
        try: s.len=MP3(fp).info.length; s.seek.configure(to=int(s.len))
        except: s.len=0; s.seek.configure(to=100)

    # ► slider preview (no reproduce) …
    def _seek_preview(s,val):
        s._update_time(float(val))

    # ► slider commit en release …
    def _seek_commit(s,evt):
        pos=s.seek.get()
        try:
            mixer.music.play(start=pos)
            s.start=time.time()-pos; s.pause_off=0; s.playing=True
            s._sync_icons(); s._update_time(pos)
        except Exception as e:
            s.info.config(text=f"Error al saltar: {e}")

    def _loop(s):
        if s.playing and mixer.music.get_busy():
            pos=time.time()-s.start
            s.seek.set(pos); s._update_time(pos); s.r.after(500,s._loop)

    def _update_time(s,cur):
        fmt=lambda x:f"{int(x//60):02}:{int(x%60):02}"
        s.time.config(text=f"{fmt(cur)} / {fmt(s.len)}")

    def _watch_end(s):
        if s.playing:
            if not mixer.music.get_busy(): s.next()
            else: s.r.after(1000,s._watch_end)

    # prev / next
    def prev(s):
        if not s.state.tracks: return
        s.state.idx=(s.state.idx-1)%len(s.state.tracks); s.pause_off=0; s.play_pause()

    def next(s):
        if not s.state.tracks: return
        s.state.idx=(s.state.idx+1)%len(s.state.tracks); s.pause_off=0; s.play_pause()

    # ─── panel Añadir a lista ──────────────────────────────────────
    def _add_toggle(s):
        if s.add_vis:
            s.add_frame.pack_forget(); s.add_vis=False; s.pending_song=None; return

        sel=s.lib.curselection()
        if not sel:
            s.info.config(text="Selecciona una canción primero"); return

        s.pending_song=s.lib.get(sel[0])               # guarda canción
        s.add_box.delete(0,tk.END)
        for p in playlists(): s.add_box.insert(tk.END,p)
        s.add_frame.pack(padx=16,fill="x"); s.add_vis=True

    def _add_confirm(s):
        sel_pl=s.add_box.curselection()
        if not sel_pl or not s.pending_song: return
        pl=s.add_box.get(sel_pl[0]); path=f"playlists/{pl}.txt"
        if s.pending_song not in pl_tracks(pl):
            with open(path,"a",encoding="utf-8") as f: f.write(s.pending_song+"\n")
            s.info.config(text=f"✓ Añadido a '{pl}'")
        s._add_toggle()

    # ─── PLAYLISTS lógica ──────────────────────────────────────────
    def _pl_play_toggle(s):
        sel=s.pl.curselection()
        if not sel: s.play_pause(); return
        pl=s.pl.get(sel[0])
        if s.current_pl!=pl:
            s.current_pl=pl; s._refresh_library(pl_tracks(pl)); s.state.idx=0
        s.pause_off=0; s.play_pause()

    def _tracks_toggle(s):
        if s.tracks_vis:
            s.tracks.pack_forget(); s.view_btn.config(text="👁 Ver"); s.tracks_vis=False; return
        sel=s.pl.curselection(); 
        if not sel: return
        pl=s.pl.get(sel[0]); songs=pl_tracks(pl)
        s.tracks.delete(0,tk.END)
        for t in songs: s.tracks.insert(tk.END,f"• {t}")
        s.tracks.pack(fill="x",padx=22,pady=(0,10))
        s.view_btn.config(text="🙈 Ocultar"); s.tracks_vis=True

    def _newpl_toggle(s):
        if s.newpl_vis:
            s.newpl_frame.pack_forget(); s.newpl_vis=False; return
        s.newpl_entry.delete(0,tk.END)
        s.newpl_frame.pack(padx=16,fill="x"); s.newpl_vis=True

    def _newpl_confirm(s):
        n=s.newpl_entry.get().strip()
        if n:
            open(f"playlists/{n}.txt","w",encoding="utf-8").close()
            s.pl.insert(tk.END,n); s._newpl_toggle()

    def _pl_delete(s):
        sel=s.pl.curselection()
        if sel:
            n=s.pl.get(sel[0]); os.remove(f"playlists/{n}.txt"); s.pl.delete(sel[0])

    def _delete_song(s):
        sel=s.lib.curselection()
        if sel:
            f=s.lib.get(sel[0]); os.remove(f"library/{f}"); s._refresh_library()
# ─── splash y lanzamiento ──────────────────────────────────────────
def launch():
    root=tk.Tk(); root.geometry("520x760"); root.configure(bg=ACCENT); root.title("Sound Loud")
    splash=tk.Frame(root,bg=ACCENT); splash.pack(expand=True,fill="both")

    logo=Image.open("music_logo.png").convert("RGBA").resize((400,400),Image.Resampling.LANCZOS)
    lbl=tk.Label(splash,bg=ACCENT); lbl.pack(expand=True)

    frames=[ImageTk.PhotoImage(logo.copy().putalpha(a) or logo) for a in range(255,0,-25)]
    def fade(i=0):
        if i<len(frames):
            lbl.config(image=frames[i]); root.after(40,lambda:fade(i+1))
        else:
            splash.destroy(); SoundLoud(root)

    lbl.config(image=ImageTk.PhotoImage(logo))
    root.after(800,fade); root.mainloop()

# ─── punto de entrada ─────────────────────────────────────────────
if __name__=="__main__":
    launch()
