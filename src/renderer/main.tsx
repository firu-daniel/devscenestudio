import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

// Composition root. Day 1 step 4 replaces `window.studio` with the getStudio() seam.
const root = document.getElementById("root");
if (!root) throw new Error("#root is missing from index.html");

createRoot(root).render(
  <StrictMode>
    <App studio={window.studio} />
  </StrictMode>,
);
