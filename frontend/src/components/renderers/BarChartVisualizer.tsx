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
	};
	metadata?: Record<string, unknown>;
}

interface BarChartVisualizerProps {
	spec: BarChartSpec;
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

const cardClass = 'bg-white rounded-lg border border-gray-200 p-4';

export default function BarChartVisualizer({ spec }: BarChartVisualizerProps) {
	if (!spec) return null;

	const chartRef = useRef<HTMLDivElement>(null);
	const rows = Array.isArray(spec.data) ? spec.data : [];
	const xKey = inferXAxisKey(rows, spec?.config?.xAxis?.key);
	const yKeys = inferYAxisKeys(
		rows,
		spec?.config?.yAxis?.map((y) => y.key),
		xKey
	);

	return (
		<div className={cardClass}>
			<div ref={chartRef}>
				{spec?.title ? (
					<h2 className="text-base font-semibold text-gray-900 mb-3">{spec.title}</h2>
				) : null}
				<div className="w-full h-[calc(60vh-2rem)] min-h-[300px]">
					<ResponsiveContainer>
						<BarChart data={rows} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
						<CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
						<XAxis
							dataKey={xKey}
							label={spec?.config?.xAxis?.label ? { value: spec.config.xAxis.label, position: 'insideBottom', offset: -5 } : undefined}
							stroke="#6b7280"
							angle={-45}
							textAnchor="end"
							height={120}
						/>
						<YAxis stroke="#6b7280" />
						<Tooltip />
						<Legend 
							verticalAlign="bottom" 
							height={50}
							wrapperStyle={{ paddingTop: '10px', paddingBottom: '10px' }}
						/>
						{yKeys.map((key, index) => (
							<Bar key={key} dataKey={key} fill={COLORS[index % COLORS.length]} radius={[4, 4, 0, 0]} />
						))}
						</BarChart>
					</ResponsiveContainer>
				</div>
			</div>
		</div>
	);
}