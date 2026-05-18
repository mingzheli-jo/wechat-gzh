import { useEffect, useRef } from "react";
import type { ImagePostTemplate } from "../../api/image-posts";

interface Props {
  panelImageUrls: string[];
  captions: string[];
  template: ImagePostTemplate;
  watermark: string;
  width?: number;
}

const TEMPLATE_SIZE: Record<ImagePostTemplate, { w: number; h: number; fontRatio: number }> = {
  two_panel_contrast: { w: 750, h: 1600, fontRatio: 0.06 },
  single_panel_caption: { w: 1024, h: 1280, fontRatio: 0.10 },
};

export function CompositionCanvas({
  panelImageUrls,
  captions,
  template,
  watermark,
  width: displayWidth,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const { w, h, fontRatio } = TEMPLATE_SIZE[template];
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // White background (drawn immediately so canvas isn't blank while loading)
    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, w, h);

    const loadPromises = panelImageUrls.map(
      (url) =>
        new Promise<HTMLImageElement>((resolve, reject) => {
          const img = new Image();
          img.crossOrigin = "anonymous";
          img.onload = () => resolve(img);
          img.onerror = reject;
          img.src = url;
        })
    );

    async function render() {
      // Ensure the bold Chinese font is loaded before drawing text
      await document.fonts.load(`bold ${Math.floor(w * fontRatio)}px "Source Han Sans SC"`);

      const imgs = await Promise.all(loadPromises);

      const baseFontSize = Math.floor(w * fontRatio);
      const margin = Math.floor(w * 0.03);
      const panelW = w - 2 * margin;
      const panelH = panelW;
      const captionBandH = Math.floor(baseFontSize * 2.2);
      const watermarkH = Math.floor(baseFontSize * 1.2);
      const panelCount = template === "two_panel_contrast" ? 2 : 1;

      const totalH =
        template === "two_panel_contrast"
          ? (captionBandH + panelH) * panelCount + watermarkH
          : Math.floor(baseFontSize * 2.5) + panelH + Math.floor(baseFontSize * 0.8);
      const startY = Math.max(0, Math.floor((h - totalH) / 2));
      let y = startY;

      ctx!.textAlign = "center";
      ctx!.textBaseline = "top";

      if (template === "two_panel_contrast") {
        for (let i = 0; i < panelCount; i++) {
          const cap = captions[i] ?? "";
          ctx!.font = `bold ${baseFontSize}px "Source Han Sans SC", sans-serif`;
          ctx!.fillStyle = "rgb(20,20,20)";
          ctx!.fillText(cap, w / 2, y + (captionBandH - baseFontSize) / 2);
          y += captionBandH;

          if (imgs[i]) ctx!.drawImage(imgs[i], margin, y, panelW, panelH);
          y += panelH;
        }
        const wmSize = Math.max(10, Math.floor(w * 0.018));
        ctx!.font = `${wmSize}px "Source Han Sans SC", sans-serif`;
        ctx!.fillStyle = "rgb(160,160,160)";
        ctx!.fillText(watermark, w / 2, h - watermarkH + (watermarkH - wmSize) / 2);
      } else {
        const bigBand = Math.floor(baseFontSize * 2.5);
        ctx!.font = `bold ${baseFontSize}px "Source Han Sans SC", sans-serif`;
        ctx!.fillStyle = "rgb(20,20,20)";
        ctx!.fillText(captions[0] ?? "", w / 2, y + (bigBand - baseFontSize) / 2);
        y += bigBand;
        if (imgs[0]) ctx!.drawImage(imgs[0], margin, y, panelW, panelH);
        y += panelH;
        const wmSize = Math.max(10, Math.floor(w * 0.018));
        ctx!.font = `${wmSize}px "Source Han Sans SC", sans-serif`;
        ctx!.fillStyle = "rgb(160,160,160)";
        ctx!.fillText(watermark, w / 2, y + (Math.floor(baseFontSize * 0.8) - wmSize) / 2);
      }
    }

    render().catch((e) => {
      console.error("CompositionCanvas render failed", e);
    });
  }, [panelImageUrls, captions, template, watermark]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: displayWidth ?? "100%",
        maxWidth: "100%",
        height: "auto",
        background: "var(--color-surface-2)",
        borderRadius: "var(--radius-md)",
      }}
    />
  );
}
