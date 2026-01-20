let chart, candleSeries;

function initChart() {
    const chartOptions = {
        layout: { textColor: '#d1d4dc', background: { type: 'solid', color: '#161b22' } },
        grid: { vertLines: { color: '#30363d' }, horzLines: { color: '#30363d' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        timeScale: { borderColor: '#30363d', timeVisible: true, secondsVisible: false }
    };
    chart = LightweightCharts.createChart(document.getElementById('chart'), chartOptions);
    candleSeries = chart.addCandlestickSeries({
        upColor: '#26a69a', downColor: '#ef5350', borderVisible: false,
        wickUpColor: '#26a69a', wickDownColor: '#ef5350',
    });
}

async function loadData() {
    const sym = document.getElementById('symbol').value;
    const date = document.getElementById('date').value;

    try {
        // Load Candles
        const cResp = await fetch(`/api/candles?symbol=${sym}&date=${date}&mode=live`);
        const cData = await cResp.json();
        if (cData.data) {
            candleSeries.setData(cData.data);
        }

        // Load Trades
        const tResp = await fetch(`/api/trades?symbol=${sym}&date=${date}`);
        const tData = await tResp.json();
        const tbody = document.querySelector('#trades-table tbody');
        tbody.innerHTML = '';

        tData.trades.forEach(t => {
            const row = tbody.insertRow();
            const pnl = t.exit_price ? ((t.exit_price - t.entry_price) / t.entry_price * 100).toFixed(2) : '-';
            const resultClass = t.outcome === 'WIN' ? 'win' : (t.outcome === 'LOSS' ? 'loss' : '');

            row.innerHTML = `
                <td>${t.entry_time}</td>
                <td>${t.pattern_id || t.strategy}</td>
                <td>${t.entry_price}</td>
                <td>${t.exit_price || 'Open'}</td>
                <td class="${resultClass}">${t.outcome || 'Active'}</td>
                <td class="${resultClass}">${pnl}%</td>
            `;
        });
    } catch (e) {
        console.error("Failed to load data:", e);
    }
}

// Ensure DOM is loaded before initializing
document.addEventListener('DOMContentLoaded', () => {
    initChart();
    loadData();
    setInterval(loadData, 60000);
});
