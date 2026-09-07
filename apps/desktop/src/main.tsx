import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// NOTE: StrictMode is intentionally NOT used here. StrictMode double-invokes
// effects/renders in development, which duplicates the r3f WebGL canvas,
// animation loops, and THREE.Clock instances, producing "THREE.Clock" errors
// and visual artifacts (double orb glow). The app is a single-window desktop
// assistant; a single mount is the correct behavior.
//
// HashRouter is owned by App.tsx — do NOT wrap it here again.
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
