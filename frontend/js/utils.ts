// import { useState } from "react";

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
