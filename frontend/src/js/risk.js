let riskPoolData = [];
let currentRiskStock = null;
let currentFilter = 'all';

document.addEventListener('DOMContentLoaded', function() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('ztDateInput').value = today;
    fetchRiskPool(true);
});
