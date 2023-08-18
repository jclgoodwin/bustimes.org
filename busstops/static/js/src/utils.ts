import { LngLatBounds } from "maplibre-gl";
import { LngLatBounds as LngLatBoundsType} from "react-map-gl/maplibre";

export const useDarkMode = () => {
  // if (window.matchMedia) {
  //   const query = window.matchMedia("(prefers-color-scheme: dark)");

  //   const [darkMode, setDarkMode] = useState(query.matches);

  //   useEffect(() => {
  //     const handleChange = (e) => {
  //       setDarkMode(e.matches);
  //     };

  //     query.addEventListener("change", handleChange);

  //     return () => {
  //       query.removeEventListener("change", handleChange);
  //     };
  //   }, []);
  // }

  return false;
};

type Stop = {
  coordinates: [number, number];
};

export function getBounds(items: Array<Stop>) {
  let bounds = new LngLatBounds();
  for (const item of items) {
    bounds.extend(item.coordinates);
  }

  return bounds as LngLatBoundsType;
}
