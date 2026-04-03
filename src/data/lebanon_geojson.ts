// Lebanon Governorates and Districts GeoJSON boundaries for risk choropleth
// Synced from backend/data/lebanon_boundaries.geojson

export type LebanonFeatureProperties = {
  id: string;
  name: string;
  name_ar: string;
  type: "governorate" | "district";
  parent?: string;
  centroid_lat: number;
  centroid_lng: number;
};

export type LebanonFeature = GeoJSON.Feature<GeoJSON.Polygon, LebanonFeatureProperties>;
export type LebanonGeoJSON = GeoJSON.FeatureCollection<GeoJSON.Polygon, LebanonFeatureProperties>;

// Canonical name → region name as used in backend risk scores
// Governorates only — used for the choropleth layer
export const REGION_NAMES: string[] = [
  "Beirut",
  "Mount Lebanon",
  "North Lebanon",
  "South Lebanon",
  "Nabatieh",
  "Bekaa",
  "Baalbek-Hermel",
  "Akkar",
];

export const LEBANON_GEOJSON: LebanonGeoJSON = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { id: "gov-beirut", name: "Beirut", name_ar: "بيروت", type: "governorate", centroid_lat: 33.8938, centroid_lng: 35.5018 },
      geometry: { type: "Polygon", coordinates: [[[35.472, 33.868], [35.535, 33.868], [35.535, 33.925], [35.472, 33.925], [35.472, 33.868]]] },
    },
    {
      type: "Feature",
      properties: { id: "gov-mount-lebanon", name: "Mount Lebanon", name_ar: "جبل لبنان", type: "governorate", centroid_lat: 33.81, centroid_lng: 35.65 },
      geometry: { type: "Polygon", coordinates: [[[35.45, 33.68], [35.8, 33.68], [35.8, 34.02], [35.45, 34.02], [35.45, 33.68]]] },
    },
    {
      type: "Feature",
      properties: { id: "gov-north", name: "North Lebanon", name_ar: "الشمال", type: "governorate", centroid_lat: 34.33, centroid_lng: 35.9 },
      geometry: { type: "Polygon", coordinates: [[[35.6, 34.15], [36.6, 34.15], [36.6, 34.69], [35.6, 34.69], [35.6, 34.15]]] },
    },
    {
      type: "Feature",
      properties: { id: "gov-south", name: "South Lebanon", name_ar: "الجنوب", type: "governorate", centroid_lat: 33.27, centroid_lng: 35.37 },
      geometry: { type: "Polygon", coordinates: [[[35.05, 33.05], [35.7, 33.05], [35.7, 33.6], [35.05, 33.6], [35.05, 33.05]]] },
    },
    {
      type: "Feature",
      properties: { id: "gov-nabatieh", name: "Nabatieh", name_ar: "النبطية", type: "governorate", centroid_lat: 33.38, centroid_lng: 35.48 },
      geometry: { type: "Polygon", coordinates: [[[35.3, 33.15], [35.78, 33.15], [35.78, 33.55], [35.3, 33.55], [35.3, 33.15]]] },
    },
    {
      type: "Feature",
      properties: { id: "gov-bekaa", name: "Bekaa", name_ar: "البقاع", type: "governorate", centroid_lat: 33.85, centroid_lng: 36.0 },
      geometry: { type: "Polygon", coordinates: [[[35.65, 33.4], [36.6, 33.4], [36.6, 34.2], [35.65, 34.2], [35.65, 33.4]]] },
    },
    {
      type: "Feature",
      properties: { id: "gov-baalbek-hermel", name: "Baalbek-Hermel", name_ar: "بعلبك الهرمل", type: "governorate", centroid_lat: 34.2, centroid_lng: 36.25 },
      geometry: { type: "Polygon", coordinates: [[[35.8, 33.9], [36.6, 33.9], [36.6, 34.7], [35.8, 34.7], [35.8, 33.9]]] },
    },
    {
      type: "Feature",
      properties: { id: "gov-akkar", name: "Akkar", name_ar: "عكار", type: "governorate", centroid_lat: 34.55, centroid_lng: 36.15 },
      geometry: { type: "Polygon", coordinates: [[[35.9, 34.45], [36.6, 34.45], [36.6, 34.7], [35.9, 34.7], [35.9, 34.45]]] },
    },
    // Districts
    {
      type: "Feature",
      properties: { id: "dist-beirut", name: "Beirut District", name_ar: "قضاء بيروت", type: "district", parent: "gov-beirut", centroid_lat: 33.8938, centroid_lng: 35.5018 },
      geometry: { type: "Polygon", coordinates: [[[35.472, 33.868], [35.535, 33.868], [35.535, 33.925], [35.472, 33.925], [35.472, 33.868]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-metn", name: "Metn", name_ar: "المتن", type: "district", parent: "gov-mount-lebanon", centroid_lat: 33.93, centroid_lng: 35.63 },
      geometry: { type: "Polygon", coordinates: [[[35.54, 33.85], [35.72, 33.85], [35.72, 34.01], [35.54, 34.01], [35.54, 33.85]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-keserwan", name: "Keserwan", name_ar: "كسروان", type: "district", parent: "gov-mount-lebanon", centroid_lat: 33.98, centroid_lng: 35.68 },
      geometry: { type: "Polygon", coordinates: [[[35.56, 33.92], [35.78, 33.92], [35.78, 34.07], [35.56, 34.07], [35.56, 33.92]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-chouf", name: "Chouf", name_ar: "الشوف", type: "district", parent: "gov-mount-lebanon", centroid_lat: 33.72, centroid_lng: 35.59 },
      geometry: { type: "Polygon", coordinates: [[[35.45, 33.62], [35.72, 33.62], [35.72, 33.82], [35.45, 33.82], [35.45, 33.62]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-aley", name: "Aley", name_ar: "عاليه", type: "district", parent: "gov-mount-lebanon", centroid_lat: 33.81, centroid_lng: 35.59 },
      geometry: { type: "Polygon", coordinates: [[[35.48, 33.75], [35.71, 33.75], [35.71, 33.88], [35.48, 33.88], [35.48, 33.75]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-baabda", name: "Baabda", name_ar: "بعبدا", type: "district", parent: "gov-mount-lebanon", centroid_lat: 33.835, centroid_lng: 35.56 },
      geometry: { type: "Polygon", coordinates: [[[35.48, 33.78], [35.66, 33.78], [35.66, 33.9], [35.48, 33.9], [35.48, 33.78]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-jbeil", name: "Jbeil (Byblos)", name_ar: "جبيل", type: "district", parent: "gov-mount-lebanon", centroid_lat: 34.11, centroid_lng: 35.65 },
      geometry: { type: "Polygon", coordinates: [[[35.58, 34.02], [35.72, 34.02], [35.72, 34.2], [35.58, 34.2], [35.58, 34.02]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-tripoli", name: "Tripoli", name_ar: "طرابلس", type: "district", parent: "gov-north", centroid_lat: 34.4364, centroid_lng: 35.8497 },
      geometry: { type: "Polygon", coordinates: [[[35.78, 34.38], [35.92, 34.38], [35.92, 34.5], [35.78, 34.5], [35.78, 34.38]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-zgharta", name: "Zgharta", name_ar: "زغرتا", type: "district", parent: "gov-north", centroid_lat: 34.396, centroid_lng: 35.9 },
      geometry: { type: "Polygon", coordinates: [[[35.82, 34.32], [36.0, 34.32], [36.0, 34.47], [35.82, 34.47], [35.82, 34.32]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-minieh-danniyeh", name: "Minieh-Danniyeh", name_ar: "المنية الضنية", type: "district", parent: "gov-north", centroid_lat: 34.4, centroid_lng: 36.0 },
      geometry: { type: "Polygon", coordinates: [[[35.9, 34.28], [36.2, 34.28], [36.2, 34.52], [35.9, 34.52], [35.9, 34.28]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-koura", name: "Koura", name_ar: "الكورة", type: "district", parent: "gov-north", centroid_lat: 34.3, centroid_lng: 35.95 },
      geometry: { type: "Polygon", coordinates: [[[35.83, 34.22], [36.05, 34.22], [36.05, 34.37], [35.83, 34.37], [35.83, 34.22]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-bcharre", name: "Bcharre", name_ar: "بشري", type: "district", parent: "gov-north", centroid_lat: 34.26, centroid_lng: 36.01 },
      geometry: { type: "Polygon", coordinates: [[[35.9, 34.18], [36.18, 34.18], [36.18, 34.35], [35.9, 34.35], [35.9, 34.18]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-sidon", name: "Sidon", name_ar: "صيدا", type: "district", parent: "gov-south", centroid_lat: 33.56, centroid_lng: 35.37 },
      geometry: { type: "Polygon", coordinates: [[[35.25, 33.45], [35.55, 33.45], [35.55, 33.65], [35.25, 33.65], [35.25, 33.45]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-tyre", name: "Tyre", name_ar: "صور", type: "district", parent: "gov-south", centroid_lat: 33.27, centroid_lng: 35.2 },
      geometry: { type: "Polygon", coordinates: [[[35.1, 33.15], [35.4, 33.15], [35.4, 33.4], [35.1, 33.4], [35.1, 33.15]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-jezzine", name: "Jezzine", name_ar: "جزين", type: "district", parent: "gov-south", centroid_lat: 33.54, centroid_lng: 35.58 },
      geometry: { type: "Polygon", coordinates: [[[35.45, 33.42], [35.7, 33.42], [35.7, 33.65], [35.45, 33.65], [35.45, 33.42]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-nabatieh", name: "Nabatieh District", name_ar: "قضاء النبطية", type: "district", parent: "gov-nabatieh", centroid_lat: 33.38, centroid_lng: 35.48 },
      geometry: { type: "Polygon", coordinates: [[[35.35, 33.28], [35.65, 33.28], [35.65, 33.5], [35.35, 33.5], [35.35, 33.28]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-hasbaya", name: "Hasbaya", name_ar: "حاصبيا", type: "district", parent: "gov-nabatieh", centroid_lat: 33.39, centroid_lng: 35.69 },
      geometry: { type: "Polygon", coordinates: [[[35.58, 33.32], [35.78, 33.32], [35.78, 33.5], [35.58, 33.5], [35.58, 33.32]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-marjayoun", name: "Marjayoun", name_ar: "مرجعيون", type: "district", parent: "gov-nabatieh", centroid_lat: 33.36, centroid_lng: 35.58 },
      geometry: { type: "Polygon", coordinates: [[[35.4, 33.25], [35.68, 33.25], [35.68, 33.48], [35.4, 33.48], [35.4, 33.25]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-bint-jbeil", name: "Bint Jbeil", name_ar: "بنت جبيل", type: "district", parent: "gov-nabatieh", centroid_lat: 33.12, centroid_lng: 35.43 },
      geometry: { type: "Polygon", coordinates: [[[35.25, 33.02], [35.6, 33.02], [35.6, 33.25], [35.25, 33.25], [35.25, 33.02]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-zahleh", name: "Zahleh", name_ar: "زحلة", type: "district", parent: "gov-bekaa", centroid_lat: 33.85, centroid_lng: 35.9 },
      geometry: { type: "Polygon", coordinates: [[[35.7, 33.75], [36.1, 33.75], [36.1, 33.98], [35.7, 33.98], [35.7, 33.75]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-west-bekaa", name: "West Bekaa", name_ar: "البقاع الغربي", type: "district", parent: "gov-bekaa", centroid_lat: 33.57, centroid_lng: 35.7 },
      geometry: { type: "Polygon", coordinates: [[[35.6, 33.38], [35.85, 33.38], [35.85, 33.75], [35.6, 33.75], [35.6, 33.38]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-rachaya", name: "Rachaya", name_ar: "راشيا", type: "district", parent: "gov-bekaa", centroid_lat: 33.5, centroid_lng: 35.85 },
      geometry: { type: "Polygon", coordinates: [[[35.7, 33.35], [36.0, 33.35], [36.0, 33.65], [35.7, 33.65], [35.7, 33.35]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-baalbek", name: "Baalbek", name_ar: "بعلبك", type: "district", parent: "gov-baalbek-hermel", centroid_lat: 34.004, centroid_lng: 36.211 },
      geometry: { type: "Polygon", coordinates: [[[35.95, 33.85], [36.5, 33.85], [36.5, 34.25], [35.95, 34.25], [35.95, 33.85]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-hermel", name: "Hermel", name_ar: "الهرمل", type: "district", parent: "gov-baalbek-hermel", centroid_lat: 34.4, centroid_lng: 36.38 },
      geometry: { type: "Polygon", coordinates: [[[36.0, 34.25], [36.6, 34.25], [36.6, 34.7], [36.0, 34.7], [36.0, 34.25]]] },
    },
    {
      type: "Feature",
      properties: { id: "dist-akkar", name: "Akkar District", name_ar: "قضاء عكار", type: "district", parent: "gov-akkar", centroid_lat: 34.55, centroid_lng: 36.15 },
      geometry: { type: "Polygon", coordinates: [[[35.9, 34.45], [36.6, 34.45], [36.6, 34.7], [35.9, 34.7], [35.9, 34.45]]] },
    },
  ],
};

// Only governorate features (for choropleth layer)
export const GOVERNORATE_FEATURES = LEBANON_GEOJSON.features.filter((f) => f.properties.type === "governorate");
