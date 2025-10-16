import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useRef } from 'react';


type YAxisConfig = {
	key: string;
	label?: string;
};

export interface BarChartSpec {
	type: 'bar';
	title?: string;
	data: Array<Record<string, string | number>>;
	config?: {
		xAxis?: { key?: string; label?: string };
		yAxis?: YAxisConfig[];
		stacked?: boolean;
	};
	metadata?: Record<string, unknown>;
}

interface BarChartVisualizerProps {
	spec: BarChartSpec;
	forceLight?: boolean;
}

function inferXAxisKey(rows: Array<Record<string, unknown>>, configuredKey?: string): string {
	if (configuredKey) return configuredKey;
	if (!rows || rows.length === 0) return '';
	const candidateKeys = Object.keys(rows[0] || {});
	return candidateKeys[0] || '';
}

function inferYAxisKeys(
	rows: Array<Record<string, unknown>>,
	configuredKeys?: string[],
	xKey?: string
): string[] {
	if (configuredKeys && configuredKeys.length > 0) return configuredKeys;
	if (!rows || rows.length === 0) return [];
	const firstRow = rows[0] || {};
	return Object.keys(firstRow).filter((k) => k !== xKey);
}

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1', '#a78bfa', '#34d399'];

const cardClass = 'bg-white dark:bg-neutral-800 rounded-lg border border-gray-200 dark:border-neutral-700 p-4';

export default function BarChartVisualizer({ spec, forceLight = false }: BarChartVisualizerProps) {
	if (!spec) return null;

	const chartRef = useRef<HTMLDivElement>(null);
	const rows = Array.isArray(spec.data) ? spec.data : [];
	const xKey = inferXAxisKey(rows, spec?.config?.xAxis?.key);
	const yKeys = inferYAxisKeys(
		rows,
		spec?.config?.yAxis?.map((y) => y.key),
		xKey
	);
	const isStacked = spec?.config?.stacked ?? false;

  const isDarkUI = typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
  const useDark = forceLight ? false : isDarkUI;
  const gridStroke = useDark ? '#404040' : '#e5e7eb'; // neutral-700 vs gray-200
  const axisStroke = useDark ? '#d4d4d4' : '#6b7280'; // neutral-300 vs gray-500
  const titleClass = 'text-base font-semibold mb-3 ' + (useDark ? 'text-neutral-100' : 'text-gray-900');
  const containerClass = forceLight ? 'bg-white rounded-lg border border-gray-200 p-4' : cardClass;

  return (
    <div className={containerClass}>
			<div ref={chartRef}>
        {spec?.title ? (
          <h2 className={titleClass}>{spec.title}</h2>
        ) : null}
				<div className="w-full h-[calc(60vh-2rem)] min-h-[300px]">
					<ResponsiveContainer>
            <BarChart data={rows} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
						<XAxis
							dataKey={xKey}
							label={spec?.config?.xAxis?.label ? { value: spec.config.xAxis.label, position: 'insideBottom', offset: -5 } : undefined}
              stroke={axisStroke}
							angle={-45}
							textAnchor="end"
							height={120}
						/>
            <YAxis stroke={axisStroke} />
						<Tooltip />
            <Legend 
							verticalAlign="bottom" 
							height={50}
							wrapperStyle={{ paddingTop: '10px', paddingBottom: '10px' }}
						/>
						{yKeys.map((key, index) => (
							<Bar 
								key={key} 
								dataKey={key} 
								fill={COLORS[index % COLORS.length]} 
								radius={[4, 4, 0, 0]}
								stackId={isStacked ? 'stack' : undefined}
							/>
						))}
						</BarChart>
					</ResponsiveContainer>
				</div>
			</div>
		</div>
	);
}