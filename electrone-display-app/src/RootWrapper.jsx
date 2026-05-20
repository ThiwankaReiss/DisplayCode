import { useEffect, useState } from "react";

const BASE_WIDTH = 800;
const BASE_HEIGHT = 480;

export default function RootWrapper({ children }) {
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const handleResize = () => {
      const scaleX = window.innerWidth / BASE_WIDTH;
      const scaleY = window.innerHeight / BASE_HEIGHT;

      // Maintain aspect ratio
      setScale(Math.min(scaleX, scaleY));
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return (
    <div
      style={{
        width: BASE_WIDTH,
        height: BASE_HEIGHT,
        transform: `scale(${scale})`,
        transformOrigin: "top left",
        overflow: "hidden"
      }}
    >
      {children}
    </div>
  );
}