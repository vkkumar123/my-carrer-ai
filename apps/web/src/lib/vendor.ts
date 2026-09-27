/**
 * Where browser runtimes (code editor, SQL, Python, face detection) are served from.
 * Default: this site's /vendor folder (filled by scripts/copy-vendor.mjs). Set
 * NEXT_PUBLIC_VENDOR_BASE_URL to serve them from object storage/CDN instead (e.g. R2).
 */
export function vendorUrl(path: string): string {
  const configured = process.env.NEXT_PUBLIC_VENDOR_BASE_URL?.replace(/\/$/, "");
  const base = configured || (typeof window !== "undefined" ? `${window.location.origin}/vendor` : "/vendor");
  return `${base}/${path.replace(/^\//, "")}`;
}
