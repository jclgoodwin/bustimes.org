// import { useState } from "react";
import { LngLatBounds } from "maplibre-gl";

export const useDarkMode = () => {
  // const query = window.matchMedia("(prefers-color-scheme: dark)");

  // const [darkMode, setDarkMode] = useState(query.matches);

  // useEffect(() => {
  //   const handleChange = (e: MediaQueryListEvent) => {
  //     setDarkMode(e.matches);
  //   };

  //   query.addEventListener("change", handleChange);

  //   return () => {
  //     query.removeEventListener("change", handleChange);
  //   };
  // }, [query]);

  // const [darkMode, _] = useState(() => {
  //   try {
  //     const mapStyle = localStorage.getItem("map-style");
  //     if (mapStyle) {
  //       return mapStyle.endsWith("_dark");
  //     }
  //   } catch {
  //     // ignore
  //   }
  //   return false;
  // });

  // return darkMode;

  return false;
};

export function getBounds<T>(
  list: Array<T> | undefined,
  key: (arg0: T) => [number, number] | null | undefined,
  initialBounds?: LngLatBounds,
) {
  if (list?.length) {
    const bounds = initialBounds || new LngLatBounds();
    list.reduce((bounds, item?) => {
      if (item) {
        const value = key(item);
        if (value) {
          bounds.extend(value);
        }
      }
      return bounds;
    }, bounds);
    return bounds;
  }
}
