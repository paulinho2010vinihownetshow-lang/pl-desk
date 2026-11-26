#!/usr/bin/env python3
"""
PL Desk - aplica a marca no codigo do RustDesk.

Roda dentro da raiz do repositorio (o seu fork do RustDesk), ja com os
submodulos baixados. O workflow do GitHub chama este script sozinho antes de
compilar, entao voce nao precisa rodar nada a mao.

Variaveis de ambiente (vem dos Secrets do GitHub):
  PL_SERVER  -> IP ou dominio do seu servidor (ex: 129.146.10.20)
  PL_KEY     -> chave publica do servidor (conteudo do id_ed25519.pub)
"""
import os
import re
import shutil
import subprocess
import sys

APP_NAME = "PLDesk"            # nome interno (sem espaco: vira nome de pasta e servico)
DISPLAY_NAME = "PL Desk"        # nome que aparece na janela e no Windows
DESCRIPTION = "PL Desk - Acesso Remoto"

ROOT = os.getcwd()

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#7170ff"/><stop offset="1" stop-color="#4b55c4"/>
  </linearGradient></defs>
  <rect x="16" y="16" width="480" height="480" rx="112" fill="url(#g)"/>
  <rect x="104" y="128" width="304" height="208" rx="24" fill="none" stroke="#f7f8f8" stroke-width="32"/>
  <path d="M208 392 H304" stroke="#f7f8f8" stroke-width="32" stroke-linecap="round"/>
  <path d="M232 196 L232 300 L262 272 L286 322 L310 310 L286 262 L326 258 Z" fill="#f7f8f8" stroke="#f7f8f8" stroke-width="10" stroke-linejoin="round"/>
</svg>
"""


def draw_icon(size):
    """Desenha o icone do PL Desk (mesmo desenho do ICON_SVG) com Pillow."""
    from PIL import Image, ImageDraw
    S = 2048  # desenha grande e reduz, pra ficar liso
    k = S / 512
    # fundo em degrade diagonal #7170ff -> #4b55c4
    grad = Image.new("RGBA", (S, S))
    gp = grad.load()
    a, b = (0x71, 0x70, 0xff), (0x4b, 0x55, 0xc4)
    for y in range(S):
        for x in range(0, S, 4):
            t = (x + y) / (2 * S)
            c = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)
            for dx in range(4):
                gp[x + dx, y] = c
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([16 * k, 16 * k, 496 * k, 496 * k], radius=112 * k, fill=255)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    w = (247, 248, 248, 255)
    d.rounded_rectangle([88 * k, 112 * k, 424 * k, 352 * k], radius=40 * k, fill=w)
    d.rounded_rectangle([120 * k, 144 * k, 392 * k, 320 * k], radius=8 * k, fill=(0, 0, 0, 0))
    # recorta o miolo do monitor revelando o degrade
    inner = Image.new("L", (S, S), 0)
    ImageDraw.Draw(inner).rounded_rectangle([120 * k, 144 * k, 392 * k, 320 * k], radius=8 * k, fill=255)
    img.paste(grad, (0, 0), inner)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([192 * k, 376 * k, 320 * k, 408 * k], radius=16 * k, fill=w)
    cursor = [(232, 196), (232, 300), (262, 272), (286, 322), (310, 310), (286, 262), (326, 258)]
    d.polygon([(x * k, y * k) for x, y in cursor], fill=w)
    d.line([(x * k, y * k) for x, y in cursor + [cursor[0]]], fill=w, width=int(10 * k), joint="curve")
    return img.resize((size, size), Image.LANCZOS)


def ensure_pillow():
    try:
        import PIL  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "pillow"])


def patch(path, replacements):
    full = os.path.join(ROOT, path)
    with open(full, encoding="utf-8") as f:
        text = f.read()
    for pattern, new, regex in replacements:
        if regex:
            text, n = re.subn(pattern, new, text)
        else:
            n = text.count(pattern)
            text = text.replace(pattern, new)
        if n == 0:
            sys.exit(f"[PL Desk] ERRO: nao achei '{pattern}' em {path}. "
                     "O RustDesk mudou; me chame pra atualizar o script.")
    with open(full, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    print(f"[PL Desk] ok  {path}")


def main():
    server = os.environ.get("PL_SERVER", "").strip()
    key = os.environ.get("PL_KEY", "").strip()
    if bool(server) != bool(key):
        sys.exit("[PL Desk] ERRO: preencha os dois secrets, PL_SERVER e PL_KEY.")
    if key and not re.fullmatch(r"[A-Za-z0-9+/=]{40,60}", key):
        sys.exit("[PL Desk] ERRO: PL_KEY nao parece uma chave valida (copie a linha inteira do id_ed25519.pub).")

    # 1. Nome do app + servidor proprio (fica gravado dentro do programa)
    cfg = [
        ('RwLock::new("RustDesk".to_owned())', f'RwLock::new("{APP_NAME}".to_owned())', False),
    ]
    if server:
        cfg += [
            (r'pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];',
             f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{server}"];', True),
            (r'pub const RS_PUB_KEY: &str = "[^"]*";',
             f'pub const RS_PUB_KEY: &str = "{key}";', True),
        ]
    patch("libs/hbb_common/src/config.rs", cfg)

    # 2. Nome que aparece nas propriedades do .exe
    patch("Cargo.toml", [
        ('ProductName = "RustDesk"', f'ProductName = "{DISPLAY_NAME}"', False),
        ('FileDescription = "RustDesk Remote Desktop"', f'FileDescription = "{DESCRIPTION}"', False),
        ('name = "RustDesk"\nidentifier', f'name = "{DISPLAY_NAME}"\nidentifier', False),
    ])
    patch("flutter/windows/runner/Runner.rc", [
        ('"FileDescription", "RustDesk Remote Desktop"', f'"FileDescription", "{DESCRIPTION}"', False),
        ('"ProductName", "RustDesk"', f'"ProductName", "{DISPLAY_NAME}"', False),
    ])
    patch("flutter/windows/runner/main.cpp", [
        ('std::wstring app_name = L"RustDesk";', f'std::wstring app_name = L"{APP_NAME}";', False),
    ])
    patch("flutter/lib/desktop/widgets/tabbar_widget.dart", [
        ('child: const Text(\n                              "RustDesk",',
         f'child: const Text(\n                              "{DISPLAY_NAME}",', False),
    ])

    # 3. Icones
    ensure_pillow()
    big = draw_icon(1024)
    for size, name in [(32, "32x32.png"), (64, "64x64.png"), (128, "128x128.png"),
                       (256, "128x128@2x.png"), (512, "icon.png"), (1024, "mac-icon.png")]:
        big.resize((size, size)).save(os.path.join(ROOT, "res", name))
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    for dest in ["res/icon.ico", "res/tray-icon.ico", "flutter/windows/runner/resources/app_icon.ico"]:
        draw_icon(256).save(os.path.join(ROOT, dest), sizes=ico_sizes)
    draw_icon(512).save(os.path.join(ROOT, "flutter/assets/icon.png"))
    with open(os.path.join(ROOT, "flutter/assets/icon.svg"), "w", encoding="utf-8") as f:
        f.write(ICON_SVG)
    print("[PL Desk] ok  icones")

    print(f"[PL Desk] marca aplicada. Servidor: {server or '(padrao, sem servidor proprio)'}")


if __name__ == "__main__":
    main()
