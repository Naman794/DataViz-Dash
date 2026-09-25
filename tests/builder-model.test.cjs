const { test } = require('node:test');
const assert = require('node:assert/strict');
const model = require('../static/js/builder-model.js');
const rows = [
  { Region: 'North', Sales: 0, Date: '2026-09-01', Note: '' },
  { Region: 'North', Sales: 20, Date: '2026-09-02T23:59:00Z', Note: 'yes' },
  { Region: 'South', Sales: null, Date: '2026-09-03', Note: null },
  { Region: 'South', Sales: 40, Date: 'invalid', Note: 'yes' },
];
test('filters compose and retain zero, excluding missing numeric values', () => {
  assert.deepEqual(model.filterRows(rows, [{ column: 'Sales', mode: 'number', minimum: 0, maximum: 20 }]), rows.slice(0, 2));
  assert.deepEqual(model.filterRows(rows, [
    { column: 'Region', mode: 'category', value: 'North' },
    { column: 'Note', mode: 'missing', behavior: 'exclude' },
  ]), [rows[1]]);
});
test('date range includes the entire end day and rejects invalid dates', () => {
  assert.deepEqual(model.filterRows(rows, [{ column: 'Date', mode: 'date', start: '2026-09-02', end: '2026-09-02' }]), [rows[1]]);
  assert.equal(model.date('2026-02-30'), null);
  assert.equal(model.date('12'), null);
  assert.equal(model.date('2024-02-29'), '2024-02-29');
});
test('field detection does not interpret numeric identifiers as dates', () => {
  assert.equal(model.fieldType({}, [{ ID: '123' }], 'ID'), 'text');
  assert.equal(model.fieldType({}, rows.slice(0, 3), 'Date'), 'date');
  assert.equal(model.fieldType({}, [], 'Date'), 'text');
});
test('empty filters retain source rows without mutation', () => {
  assert.deepEqual(model.filterRows(rows, []), rows);
  assert.equal(model.filterRows(rows, [{ column: 'Note', mode: 'missing', behavior: 'only' }]).length, 2);
  assert.equal(rows.length, 4);
});
test('field drops choose appropriate charts and preserve existing layout', () => {
  assert.equal(model.chartFromField(null, 'Sales', 'number').type, 'histogram');
  assert.equal(model.chartFromField(null, 'Region', 'text').aggregation, 'count');
  assert.equal(model.chartFromField(null, 'Date', 'date').type, 'line');
  const original = { id: 'a', title: 'Revenue', type: 'bar', x: 'Region', y: null, aggregation: 'count', layout: {x: 3, y: 2, w: 6, h: 7} };
  const updated = model.chartFromField(original, 'Sales', 'number');
  assert.equal(updated.y, 'Sales');
  assert.equal(updated.aggregation, 'sum');
  assert.deepEqual(updated.layout, original.layout);
  assert.equal(updated.title, 'Revenue');
  assert.equal(original.y, null);
  const histogram = model.chartFromField(null, 'Sales', 'number');
  const category = model.chartFromField(histogram, 'Region', 'text');
  assert.equal(category.type, 'bar');
  assert.equal(category.aggregation, 'count');
  assert.equal(category.y, null);
});
