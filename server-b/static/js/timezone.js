(function() {
  function getStoredTimeZone() {
    return localStorage.getItem('timezone');
  }

  function detectTimeZone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch (e) {
      return 'UTC';
    }
  }

  function getTimeZone() {
    return getStoredTimeZone() || detectTimeZone();
  }

  function formatToTimeZone(utcString, timeZone) {
    const date = new Date(utcString);
    const formatter = new Intl.DateTimeFormat('en-GB', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
    const parts = formatter.formatToParts(date);
    const values = Object.fromEntries(parts.map(p => [p.type, p.value]));
    return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}`;
  }

  function convertTimes() {
    const tz = getTimeZone();
    document.querySelectorAll('.utc-time').forEach(el => {
      const utc = el.getAttribute('data-utc');
      if (utc) {
        el.textContent = formatToTimeZone(utc, tz);
      }
    });
  }

  function populateSelect() {
    const select = document.getElementById('timezone-select');
    if (!select) return;
    const zones = Intl.supportedValuesOf ? Intl.supportedValuesOf('timeZone') : [detectTimeZone()];
    zones.forEach(z => {
      const opt = document.createElement('option');
      opt.value = z;
      opt.textContent = z;
      select.appendChild(opt);
    });
    select.value = getTimeZone();
    select.addEventListener('change', () => {
      localStorage.setItem('timezone', select.value);
      convertTimes();
    });
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
      populateSelect();
      convertTimes();
    });
  }

  if (typeof module !== 'undefined') {
    module.exports = { formatToTimeZone };
  }
})();
