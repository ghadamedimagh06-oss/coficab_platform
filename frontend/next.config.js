/** @type {import('next').NextConfig} */
const nextConfig = {
  // Disabled to work around react-leaflet's incompatibility with React 18
  // StrictMode's dev-only double-mount, which throws "Map container is already
  // initialized" when a <MapContainer> re-attaches to an existing Leaflet node.
  // This only affects `next dev`; production builds never double-invoke. Re-enable
  // if react-leaflet is upgraded/replaced with a StrictMode-safe map.
  reactStrictMode: false,
};

module.exports = nextConfig;
