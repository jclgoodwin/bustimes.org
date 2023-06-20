import { useState, useEffect } from "react";

export const useDarkMode = () => {
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    if (window.matchMedia) {
      let query = window.matchMedia("(prefers-color-scheme: dark)");
      if (query.matches) {
        setDarkMode(true);
      }

      const handleChange = (e) => {
        setDarkMode(e.matches);
      };

      query.addEventListener("change", handleChange);

      return () => {
        query.removeEventListener("change", handleChange);
      };
    }
  }, []);

  return darkMode;
};
