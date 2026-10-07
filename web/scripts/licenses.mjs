import { mkdir, copyFile } from "node:fs/promises";
const directory = new URL("../../webapp/static/licenses/", import.meta.url);
await mkdir(directory, { recursive: true });
for (const [source, target] of [
  ["@fontsource-variable/public-sans/LICENSE", "public-sans.txt"],
  ["react/LICENSE", "react.txt"],
  ["react-dom/LICENSE", "react-dom.txt"],
  ["lucide-react/LICENSE", "lucide.txt"],
  ["react-markdown/license", "react-markdown.txt"],
  ["remark-gfm/license", "remark-gfm.txt"],
]) {
  await copyFile(
    new URL(`../node_modules/${source}`, import.meta.url),
    new URL(target, directory),
  );
}
