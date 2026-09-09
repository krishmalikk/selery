const assert=require('node:assert/strict');
const decode=require('../packages/uri-decoder/index.cjs');
assert.equal(decode('SPY%2FQQQ'),'SPY/QQQ');
assert.equal(decode('%F0%9F%8C%B1'),'🌱');
assert.equal(decode('%C2'),'%'+'C2');
const malformed='%FF'.repeat(100000);assert.equal(decode(malformed),malformed);
assert.throws(()=>decode(null),TypeError);
console.log('Bounded URI decoder behavior passed');
