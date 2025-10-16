import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import React, { useRef } from 'react';

type PieVariant = 'simple' | 'donut' | 'two-level' | 'straight-angle';

type PieConfig = {
    variant?: PieVariant;
    categoryKey?: string;
    valueKey?: string;
    innerRadius?: number;
    outerRadius?: number;
    showPercentage?: boolean;
    showLabels?: boolean;
    paddingAngle?: number;
    nested?: {
        enabled: boolean;
        innerData: Array<Record<string, any>>;
        outerData: Array<Record<string, any>>;
    };
    multiple?: {
        enabled: boolean;
        pies: Array<{
            data: Array<Record<string, any>>;
            cx: string;
            title: string;
        }>;
    };
};

export interface PieChartSpec {
	type: 'pie';
	title?: string;
	data: Array<Record<string, string | number>>;
	config?: PieConfig;
	metadata?: Record<string, unknown>;
}

interface PieChartVisualizerProps {
	spec: PieChartSpec;
}

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff7c7c', '#8dd1e1', '#a78bfa', '#34d399'];

const cardClass = 'bg-white dark:bg-neutral-800 rounded-lg border border-gray-200 dark:border-neutral-700 p-4';


// Helper to render labels based on configuration
interface LabelProps {
    payload: Record<string, any>;
    percent?: number;
}

const renderLabel = (props: LabelProps, config: PieConfig | undefined, categoryKey: string) => {
    const name = props.payload[categoryKey];
    if (config?.showPercentage && typeof props.percent === 'number') {
        return `${name} ${(props.percent * 100).toFixed(0)}%`;
    }
    return name;
};

function inferCategoryKey(rows: Array<Record<string, unknown>>, configuredKey?: string): string {
	if (configuredKey) return configuredKey;
	if (!rows || rows.length === 0) return '';
	const candidateKeys = Object.keys(rows[0] || {});
	return candidateKeys.find((k) => typeof (rows[0] as any)[k] === 'string') || candidateKeys[0] || '';
}

function inferValueKey(rows: Array<Record<string, unknown>>, configuredKey?: string, categoryKey?: string): string {
	if (configuredKey) return configuredKey;
	if (!rows || rows.length === 0) return '';
	const candidateKeys = Object.keys(rows[0] || {});
	return candidateKeys.find((k) => k !== categoryKey && typeof (rows[0] as any)[k] === 'number') || candidateKeys.find((k) => k !== categoryKey) || '';
}

export default function PieChartVisualizer({ spec }: PieChartVisualizerProps) {
    if (!spec) return null;
    
    const chartRef = useRef<HTMLDivElement>(null);
    const rows = Array.isArray(spec.data) ? spec.data : [];
    const categoryKey = inferCategoryKey(rows, spec?.config?.categoryKey);
    const valueKey = inferValueKey(rows, spec?.config?.valueKey, categoryKey);

    // Get configuration values with defaults
    const variant = spec.config?.variant || 'simple';
    const innerRadius = spec.config?.innerRadius ?? (variant === 'donut' ? 60 : 0);
    const outerRadius = spec.config?.outerRadius ?? 150;
    const paddingAngle = spec.config?.paddingAngle ?? 0;
    const showLabels = spec.config?.showLabels ?? true;

    // Render different pie chart variants
    const renderPieChart = () => {
        switch (variant) {
            case 'two-level':
                const innerData = spec.config?.nested?.innerData || [];
                const outerData = spec.config?.nested?.outerData || [];
            
                // Create color map for parent categories
                const parentColorMap = new Map(
                    innerData.map((item, index) => [
                        item.name || item[categoryKey],
                        COLORS[index % COLORS.length]
                    ])
                );

                return (
                  <>
                        <Pie
                            data={innerData}
                            dataKey="count"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            outerRadius={90}
                            fill="#8884d8"
                            label={showLabels}
                        >
                            {innerData.map((entry, index) => (
                                <Cell 
                                    key={`cell-inner-${index}`} 
                                    fill={COLORS[index % COLORS.length]} 
                                />
                            ))}
                        </Pie>
                        <Pie
                            data={outerData}
                            dataKey="count"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={90}
                            outerRadius={120}
                            fill="#82ca9d"
                            label={showLabels}
                        >
                            {outerData.map((entry, index) => (
                                <Cell 
                                    key={`cell-outer-${index}`} 
                                    fill={parentColorMap.get(entry.parent) || COLORS[(index + 3) % COLORS.length]} 
                                    fillOpacity={0.7}
                                />
                            ))}
                        </Pie>
                    </>
                );
            
            
            case 'straight-angle':
                return (
                    <Pie
                        data={rows}
                        cx="50%"
                        cy="50%"
                        startAngle={0}
                        endAngle={180}
                        innerRadius={innerRadius}
                        outerRadius={outerRadius}
                        fill="#8884d8"
                        dataKey={valueKey}
                        nameKey={categoryKey}
                        label={showLabels ? (props) => renderLabel(props, spec.config, categoryKey) : false}
                        labelLine={showLabels}
                        paddingAngle={paddingAngle}
                    >
                        {rows.map((_, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                    </Pie>
                );
            
            default: // simple or donut
                return (
                    <Pie
                        data={rows}
                        cx="50%"
                        cy="50%"
                        innerRadius={innerRadius}
                        outerRadius={outerRadius}
                        fill="#8884d8"
                        dataKey={valueKey}
                        nameKey={categoryKey}
                        label={showLabels ? (props) => renderLabel(props, spec.config, categoryKey) : false}
                        labelLine={showLabels}
                        paddingAngle={paddingAngle}
                    >
                        {rows.map((_, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                    </Pie>
                );
        }
    };

    return (
        <div className={cardClass}>
            <div ref={chartRef}>
                {spec?.title && (
                    <h2 className="text-base font-semibold text-gray-900 dark:text-neutral-100 mb-3">{spec.title}</h2>
                )}

                <div className="w-full h-[calc(60vh-2rem)] min-h-[300px]">
				<ResponsiveContainer width="100%" height="100%">
                        <PieChart margin={{ top: 20, right: 20, left: 20, bottom: 50 }}>
                            {renderPieChart()}
                            <Tooltip />
                            <Legend 
                                verticalAlign="middle" 
                                align="right"
                                width={120}
                                wrapperStyle={{ 
                                    paddingLeft: '10px',
                                    fontSize: '10px'
                                }}
                            />
                        </PieChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
}


