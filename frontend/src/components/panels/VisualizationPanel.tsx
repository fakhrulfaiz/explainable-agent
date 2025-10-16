import React, { useCallback, useEffect, useRef, useState } from 'react';
import '../../styles/scrollbar.css';
import BarChartVisualizer, { BarChartSpec } from '../visualizers/BarChartVisualizer';
import PieChartVisualizer, { PieChartSpec } from '../visualizers/PieChartVisualizer';
import LineChartVisualizer, { LineChartSpec } from '../visualizers/LineChartVisualizer';
import { Download } from 'lucide-react';
import { useUIState } from '../../contexts/UIStateContext';

type VisualizationPanelProps = {
	open: boolean;
	onClose: () => void;
    charts: (BarChartSpec | PieChartSpec | LineChartSpec) | Array<BarChartSpec | PieChartSpec | LineChartSpec>;
	initialWidthPx?: number;
	minWidthPx?: number;
	maxWidthPx?: number;
};

const VisualizationPanel: React.FC<VisualizationPanelProps> = ({ open, onClose, charts, initialWidthPx = 900, minWidthPx = 360, maxWidthPx = 1600 }) => {
	const { state } = useUIState();
	const { isDarkMode } = state;
	
	// Convert charts to array and handle selection
    const chartsArray: Array<BarChartSpec | PieChartSpec | LineChartSpec> = Array.isArray(charts) ? charts : charts ? [charts] : [];
	const [selectedChartIndex, setSelectedChartIndex] = useState(0);
	const chartRefs = useRef<(HTMLDivElement | null)[]>([]);
	const getResponsiveWidth = () => {
		const screenWidth = window.innerWidth;
		if (screenWidth <= 768) {
			return Math.min(screenWidth - 32, maxWidthPx);
		} else if (screenWidth <= 1280) {
			return Math.min(screenWidth * 0.9, maxWidthPx);
		}
		return Math.min(initialWidthPx, maxWidthPx);
	};

	const [width, setWidth] = useState<number>(getResponsiveWidth());
	const isResizingRef = useRef<boolean>(false);

	const onMouseMove = useCallback((e: MouseEvent) => {
		if (!isResizingRef.current) return;
		const newWidth = Math.min(Math.max(window.innerWidth - e.clientX, minWidthPx), maxWidthPx);
		setWidth(newWidth);
	}, [minWidthPx, maxWidthPx]);

	const handleWindowResize = useCallback(() => {
		if (!isResizingRef.current) {
			setWidth(getResponsiveWidth());
		}
	}, []);

	const onMouseUp = useCallback(() => {
		isResizingRef.current = false;
		document.body.style.cursor = '';
		document.body.style.userSelect = '';
	}, []);

	const startResize = useCallback((e: React.MouseEvent) => {
		e.preventDefault();
		isResizingRef.current = true;
		document.body.style.cursor = 'col-resize';
		document.body.style.userSelect = 'none';
	}, []);

	useEffect(() => {
		window.addEventListener('mousemove', onMouseMove);
		window.addEventListener('mouseup', onMouseUp);
		window.addEventListener('resize', handleWindowResize);
		return () => {
			window.removeEventListener('mousemove', onMouseMove);
			window.removeEventListener('mouseup', onMouseUp);
			window.removeEventListener('resize', handleWindowResize);
		};
	}, [onMouseMove, onMouseUp, handleWindowResize]);

	const handleDownload = async () => {
		const activeChart = chartsArray[selectedChartIndex];
		if (!activeChart) return;

		const hostEl = chartRefs.current[selectedChartIndex];
		if (!hostEl) return;

		// Prefer capturing the inner container that holds the title + chart (exclude outer card paddings/borders)
		let captureEl: HTMLElement = hostEl;
		const titleEl = hostEl.querySelector('h2');
		if (titleEl && titleEl.parentElement) {
			console.log('titleEl', titleEl);
			captureEl = titleEl.parentElement as HTMLElement;
		} else {
			// Fallback to chart area only
			console.log('hostEl', hostEl);
			captureEl = (hostEl.querySelector('.recharts-wrapper') as HTMLElement) || hostEl;
		}

		try {
			const htmlToImage = await import('html-to-image');
			// Match exported background to current theme (light/dark)
			const isDark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
			const exportBg = isDark ? '#171717' : '#ffffff'; // neutral-900 for dark
			const dataUrl = await htmlToImage.toPng(captureEl, { 
				backgroundColor: exportBg,
				pixelRatio: 2,
				quality: 1
			});
			
			const link = document.createElement('a');
			link.download = `${activeChart.title || 'chart'}.png`;
			link.href = dataUrl;
			link.click();
		} catch (error) {
			console.error('Error converting chart to image:', error);
		}
	};

	return (
		<div
			className={`fixed top-0 right-0 h-full bg-white dark:bg-neutral-900 shadow-xl border-l border-gray-200 dark:border-neutral-700 transform transition-transform duration-300 ease-in-out z-40 ${open ? 'translate-x-0' : 'translate-x-full'}`}
			style={{ width }}
		>
			<div
				onMouseDown={startResize}
				className="absolute left-0 top-0 h-full w-1 cursor-col-resize bg-transparent hover:bg-gray-200/50 hidden sm:block"
				aria-label="Resize"
			/>

			<div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-900">
				<h3 className="font-semibold text-gray-900 dark:text-white">Visualization</h3>
				<div className="flex items-center gap-2">
					<button
						onClick={handleDownload}
						className="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-700 dark:text-neutral-200 bg-white dark:bg-neutral-800 border border-gray-300 dark:border-neutral-700 rounded-md hover:bg-gray-50 dark:hover:bg-neutral-700 focus:outline-none focus:ring-0"
						aria-label="Download chart"
					>
						<Download className="h-4 w-4 mr-2" />
						Download
					</button>
					<button
						onClick={onClose}
						className="px-3 py-2 rounded bg-gray-200 dark:bg-neutral-700 hover:bg-gray-300 dark:hover:bg-neutral-600 text-gray-800 dark:text-white text-sm sm:text-sm min-h-[36px] touch-manipulation"
						aria-label="Close panel"
					>
						Close
					</button>
				</div>
			</div>

			<div
				className="p-4 h-[calc(100%-56px)] slim-scroll text-gray-900 dark:text-neutral-200"
				style={{
					overflowY: 'overlay' as any,
					scrollbarWidth: 'thin',
					scrollbarColor: isDarkMode ? '#525252 transparent' : '#d1d5db transparent',
				}}
			>
				{chartsArray.length === 0 ? (
					<div className="text-gray-500 dark:text-neutral-400 text-base">No charts to display.</div>
				) : (
					<div className="space-y-4">
						{chartsArray.length > 1 && (
							<div className="bg-gray-50 dark:bg-neutral-800 rounded-lg p-6 border border-gray-200 dark:border-neutral-700 shadow-sm">
								<h2 className="text-xl font-semibold text-gray-600 dark:text-neutral-300 mb-4">Select Chart</h2>
								<div className="flex gap-3 flex-wrap">
									{chartsArray.map((chart, idx) => (
										<button
											key={idx}
											onClick={() => setSelectedChartIndex(idx)}
											className={`px-4 py-2 rounded-lg font-medium transition-colors border ${
												selectedChartIndex === idx
													? 'bg-blue-600 text-white border-blue-600'
													: 'bg-white dark:bg-neutral-900 text-gray-400 dark:text-neutral-300 border-gray-300 dark:border-neutral-700 hover:bg-gray-50 dark:hover:bg-neutral-800'
											}`}
										>
											{chart.title || `Chart ${idx + 1}`}
										</button>
									))}
								</div>
							</div>
						)}
						{(() => {
							const active = chartsArray[Math.min(selectedChartIndex, chartsArray.length - 1)];
							if (!active) return null;
							if (active.type === 'bar') {
								return (
									<div 
										ref={(el) => { chartRefs.current[selectedChartIndex] = el; }}
										className="w-full" 
										style={{ height: 700 }}
									>
										<BarChartVisualizer spec={active} />
									</div>
								);
							}
							if (active.type === 'pie') {
								return (
									<div 
										ref={(el) => { chartRefs.current[selectedChartIndex] = el; }}
										className="w-full" 
										style={{ height: 600 }}
									>
										<PieChartVisualizer spec={active} />
									</div>
								);
							}
                            if (active.type === 'line') {
                                return (
                                    <div 
										ref={(el) => { chartRefs.current[selectedChartIndex] = el; }}
										className="w-full" 
										style={{ height: 700 }}
									>
                                        <LineChartVisualizer spec={active} />
                                    </div>
                                );
                            }
							return null;
						})()}
					</div>
				)}
			</div>
		</div>
	);
};

export default VisualizationPanel;


