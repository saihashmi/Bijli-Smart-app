/** Save the chart inside an element as a PNG. Works on the SVG that is on screen; nothing is re-calculated. */
export async function exportChartPng(
  container: HTMLElement,
  opts: { title: string; background: string; text: string; fileName: string },
): Promise<void> {
  const svg = container.querySelector<SVGSVGElement>("svg.recharts-surface");
  if (!svg) throw new Error("This widget has no chart image to save.");
  const { width, height } = svg.getBoundingClientRect();
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(width));
  clone.setAttribute("height", String(height));
  clone.setAttribute("font-family", "Inter, system-ui, sans-serif");
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const img = new Image();
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("The chart could not be rendered as an image."));
      img.src = url;
    });
    const scale = 2;
    const pad = 20;
    const header = 44;
    const canvas = document.createElement("canvas");
    canvas.width = (width + pad * 2) * scale;
    canvas.height = (height + header + pad * 2) * scale;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("This browser cannot create images.");
    ctx.scale(scale, scale);
    ctx.fillStyle = opts.background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = opts.text;
    ctx.font = "600 16px Inter, system-ui, sans-serif";
    ctx.textBaseline = "middle";
    ctx.fillText(opts.title, pad, pad + 12, width);
    ctx.drawImage(img, pad, pad + header, width, height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("The image could not be created.");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = opts.fileName;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function safeFileName(title: string): string {
  return (title.replace(/[^A-Za-z0-9 _-]+/g, "").trim().replace(/\s+/g, "-").slice(0, 60) || "chart") + ".png";
}
