import asyncio
from uuid import UUID
from dataclasses import dataclass

@dataclass
class DummyVlcc:
    user_id: UUID
    name: str

@dataclass
class RateChartListDto:
    id: UUID
    chart_name: str

async def test():
    # Mocking what the controller does:
    rate_charts = [
        RateChartListDto(id=UUID('29ddf360-d9f5-4bab-a8de-6175c0240dfe'), chart_name='RC 1'),
        RateChartListDto(id=UUID('c13344f5-efbe-49de-8683-c2792dddbf7d'), chart_name='Ratechat 2')
    ]
    
    options = ['<option value="">Select Rate Chart (Optional)</option>']
    for chart in rate_charts:
        options.append(f'<option value="{chart.id}">{chart.chart_name}</option>')
    
    print("GENERATED:")
    print("\n".join(options))

asyncio.run(test())
