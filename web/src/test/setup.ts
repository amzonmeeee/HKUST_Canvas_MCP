import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
window.scrollTo = vi.fn();
HTMLElement.prototype.scrollIntoView = vi.fn();
// jsdom has no layout engine; browser tests exercise actual measurements.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
