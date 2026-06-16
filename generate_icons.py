#!/usr/bin/env python3
"""
favicon.svg から各種アイコンファイルを生成する
- apple-touch-icon.png (180x180) - iOS ホーム画面
- favicon-192.png (192x192)      - Android ホーム画面
- favicon-512.png (512x512)      - PWA / スプラッシュ
"""
import struct
import zlib
from pathlib import Path

def make_png(size: int, out_path: str):
    """Pillowなしで「廃」アイコンPNGを生成（cairo風SVGラスタライザ使用を優先、なければcairosvg）"""
    try:
        import cairosvg
        svg_path = Path("favicon.svg").read_text(encoding="utf-8")
        cairosvg.svg2png(
            bytestring=svg_path.encode(),
            write_to=out_path,
            output_width=size,
            output_height=size,
        )
        print(f"[INFO] {out_path} ({size}x{size}) 生成完了 (cairosvg)")
        return
    except ImportError:
        pass

    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        # 背景グラデーション（赤系）
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 角丸矩形（背景）
        radius = int(size * 0.18)
        # グラデーション近似: 上が明るい赤、下が暗い赤
        for y in range(size):
            t = y / size
            r = int(122 + (61 - 122) * t)
            g = int(16 + (8 - 16) * t)
            b = int(16 + (8 - 16) * t)
            draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

        # 角丸マスクを適用
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
        img.putalpha(mask)

        # 枠線
        border = max(2, int(size * 0.03))
        draw.rounded_rectangle(
            [border // 2, border // 2, size - border // 2 - 1, size - border // 2 - 1],
            radius=radius,
            outline=(192, 57, 43, 255),
            width=border,
        )

        # 「廃」文字
        font_size = int(size * 0.66)
        font = None
        for fname in [
            "C:/Windows/Fonts/YuGothB.ttc",
            "C:/Windows/Fonts/msgothic.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
            "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        ]:
            try:
                font = ImageFont.truetype(fname, font_size)
                break
            except (IOError, OSError):
                continue

        text = "廃"
        gold = (246, 173, 85, 255)

        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = (size - tw) // 2 - bbox[0]
            ty = (size - th) // 2 - bbox[1] + int(size * 0.02)
            # グロー効果（薄いオレンジを後ろに重ねる）
            from PIL import ImageFilter
            glow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_layer)
            glow_draw.text((tx, ty), text, font=font, fill=(246, 173, 85, 100))
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=size * 0.03))
            img = Image.alpha_composite(img, glow_layer)
            draw = ImageDraw.Draw(img)
            draw.text((tx, ty), text, font=font, fill=gold)
        else:
            # フォント取得失敗時はデフォルトフォント
            draw.text((size // 4, size // 6), text, fill=gold)

        img.save(out_path, "PNG")
        print(f"[INFO] {out_path} ({size}x{size}) 生成完了 (Pillow)")
        return
    except ImportError:
        pass

    print(f"[WARN] {out_path}: cairosvg も Pillow も利用不可。スキップします。")


def main():
    Path("icons").mkdir(exist_ok=True)

    make_png(180, "apple-touch-icon.png")
    make_png(192, "icons/favicon-192.png")
    make_png(512, "icons/favicon-512.png")


if __name__ == "__main__":
    main()
