// Babel configuration for the Odysseus mobile app (Expo SDK 51, plain JS).
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
  };
};
