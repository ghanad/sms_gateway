const assert = require('assert');
const { formatToTimeZone } = require('../server-b/static/js/timezone');

const utc = '2024-01-01T12:00:00Z';
const ny = formatToTimeZone(utc, 'America/New_York');
assert.strictEqual(ny, '2024-01-01 07:00');

const la = formatToTimeZone(utc, 'America/Los_Angeles');
assert.strictEqual(la, '2024-01-01 04:00');

console.log('Timezone tests passed');
