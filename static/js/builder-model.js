/* Dashboard data helpers. DataViz Dash — Naman Sinha. */
(function (root) {
  const missing = (value) => value == null || (typeof value === 'string' && value.trim() === '');
  function date(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:$|[T ])/.test(value)) return null;
    const day = value.slice(0, 10);
    const parsed = new Date(`${day}T00:00:00Z`);
    return Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== day ? null : day;
  }
  function filterRows(rows, filters) {
    return rows.filter((row) => filters.every((filter) => {
      const value = row[filter.column];
      if (filter.mode === 'missing') return filter.behavior === 'only' ? missing(value) : !missing(value);
      if (missing(value)) return false;
      if (filter.mode === 'category') return String(value) === filter.value;
      if (filter.mode === 'number') {
        const number = Number(value);
        return Number.isFinite(number) && (filter.minimum == null || number >= filter.minimum)
          && (filter.maximum == null || number <= filter.maximum);
      }
      if (filter.mode === 'date') {
        const day = date(value);
        return day !== null && (!filter.start || day >= filter.start) && (!filter.end || day <= filter.end);
      }
      return false;
    }));
  }
  function fieldType(dataset, rows, column) {
    const declared = dataset?.column_types?.[column];
    if (declared === 'number' || declared === 'date') return declared;
    const samples = rows.map((row) => row[column]).filter((value) => !missing(value)).slice(0, 100);
    return samples.length && samples.every((value) => date(value)) ? 'date' : 'text';
  }
  function chartFromField(existing, column, type, role) {
    if (!existing) return { title: type === 'number' ? `Distribution of ${column}` : `Count by ${column}`, type: type === 'number' ? 'histogram' : (type === 'date' ? 'line' : 'bar'), x: column, y: null, aggregation: type === 'number' ? 'none' : 'count', sort: 'default', top_n: 0, date_group: 'none', table_bars: true };
    const chart = { ...existing };
    if (chart.type === 'histogram') {
      chart.x = column;
      if (type !== 'number') { chart.type = type === 'date' ? 'line' : 'bar'; chart.aggregation = 'count'; }
      chart.y = null;
    } else if (type === 'number' && role !== 'category') {
      chart.y = column;
      if (!['table', 'scatter'].includes(chart.type) && ['none', 'count'].includes(chart.aggregation)) chart.aggregation = 'sum';
    } else {
      chart.x = column;
      chart.date_group = 'none';
    }
    return chart;
  }
  const model = { missing, date, filterRows, fieldType, chartFromField };
  if (typeof module !== 'undefined' && module.exports) module.exports = model;
  else root.BuilderModel = model;
})(typeof globalThis !== 'undefined' ? globalThis : this);
