'use strict';
/** Native decoding has bounded work; malformed sequences are preserved instead of recursively retried. */
module.exports = function decode(input) {
  if (typeof input !== 'string') throw new TypeError('Expected a string');
  try { return decodeURIComponent(input); } catch { return input; }
};
