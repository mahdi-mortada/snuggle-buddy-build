import { jsPDF } from 'jspdf';
import type { Alert, DashboardStats, Incident, OfficialFeedPost, RiskScore } from '@/types/crisis';

const REPORT_TITLE = 'CrisisShield \u2013 Situation Overview Report';
const DASH = '-';

type HorizontalAlign = 'left' | 'center' | 'right';

type TableColumn = {
  header: string;
  width: number;
  align?: HorizontalAlign;
};

export type DashboardPdfPayload = {
  stats: DashboardStats;
  alerts: Alert[];
  recentIncidents: Incident[];
  officialFeedHighlights: OfficialFeedPost[];
  riskScores: RiskScore[];
  exportedAt?: Date;
};

function formatDateTime(value: Date | string): string {
  const date = value instanceof Date ? value : new Date(value);
  if (!Number.isFinite(date.getTime())) {
    return DASH;
  }
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatFilenameTimestamp(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  const hours = String(value.getHours()).padStart(2, '0');
  const minutes = String(value.getMinutes()).padStart(2, '0');
  return `${year}${month}${day}-${hours}${minutes}`;
}

function sortByDateDesc<T>(items: T[], getDate: (item: T) => string): T[] {
  return [...items].sort((left, right) => {
    const leftTime = new Date(getDate(left)).getTime();
    const rightTime = new Date(getDate(right)).getTime();
    return (Number.isFinite(rightTime) ? rightTime : 0) - (Number.isFinite(leftTime) ? leftTime : 0);
  });
}

function textCell(value: unknown): string {
  if (value === null || value === undefined) {
    return DASH;
  }
  const text = String(value).replace(/\s+/g, ' ').trim();
  return text.length > 0 ? text : DASH;
}

export function exportDashboardPdf(payload: DashboardPdfPayload): void {
  console.log('PDF FUNCTION STARTED', payload);
  const exportedAt = payload.exportedAt ?? new Date();
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'pt',
    format: 'a4',
  });
  console.log('PDF INSTANCE CREATED');

  const margin = 40;
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const contentWidth = pageWidth - margin * 2;
  const lineHeight = 11;
  const cellPaddingX = 4;
  const cellPaddingY = 4;
  const tableHeaderHeight = 18;

  let cursorY = margin;

  const ensureSpace = (heightNeeded: number) => {
    if (cursorY + heightNeeded <= pageHeight - margin) {
      return;
    }
    doc.addPage();
    cursorY = margin;
  };

  const drawSectionTitle = (title: string) => {
    ensureSpace(22);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(12);
    doc.setTextColor(20, 25, 38);
    doc.text(title, margin, cursorY);
    cursorY += 8;
    doc.setDrawColor(210, 215, 225);
    doc.line(margin, cursorY, margin + contentWidth, cursorY);
    cursorY += 12;
  };

  const drawParagraph = (text: string, fontSize = 10) => {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(fontSize);
    doc.setTextColor(40, 45, 60);
    const lines = doc.splitTextToSize(textCell(text), contentWidth) as string[];
    const blockHeight = lines.length * lineHeight + 4;
    ensureSpace(blockHeight);
    doc.text(lines, margin, cursorY);
    cursorY += blockHeight;
  };

  const drawTable = (columns: TableColumn[], rows: string[][]) => {
    const drawHeader = () => {
      ensureSpace(tableHeaderHeight + 6);
      doc.setFillColor(245, 247, 250);
      doc.rect(margin, cursorY, contentWidth, tableHeaderHeight, 'F');
      doc.setDrawColor(220, 225, 235);
      doc.rect(margin, cursorY, contentWidth, tableHeaderHeight);
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(9);
      doc.setTextColor(30, 35, 50);

      let x = margin;
      columns.forEach((column) => {
        const headerY = cursorY + 12;
        if (column.align === 'right') {
          doc.text(column.header, x + column.width - cellPaddingX, headerY, { align: 'right' });
        } else if (column.align === 'center') {
          doc.text(column.header, x + column.width / 2, headerY, { align: 'center' });
        } else {
          doc.text(column.header, x + cellPaddingX, headerY);
        }
        x += column.width;
      });
      cursorY += tableHeaderHeight;
    };

    drawHeader();

    if (rows.length === 0) {
      const emptyHeight = 18;
      ensureSpace(emptyHeight);
      doc.setDrawColor(220, 225, 235);
      doc.rect(margin, cursorY, contentWidth, emptyHeight);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9);
      doc.setTextColor(85, 90, 105);
      doc.text('No records available.', margin + cellPaddingX, cursorY + 12);
      cursorY += emptyHeight + 12;
      return;
    }

    rows.forEach((row) => {
      const wrappedCells = columns.map((column, index) => {
        const rawValue = textCell(row[index] ?? DASH);
        return doc.splitTextToSize(rawValue, column.width - cellPaddingX * 2) as string[];
      });
      const maxLines = Math.max(...wrappedCells.map((cellLines) => Math.max(cellLines.length, 1)));
      const rowHeight = maxLines * lineHeight + cellPaddingY * 2;

      if (cursorY + rowHeight > pageHeight - margin) {
        doc.addPage();
        cursorY = margin;
        drawHeader();
      }

      doc.setDrawColor(225, 230, 238);
      doc.rect(margin, cursorY, contentWidth, rowHeight);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(9);
      doc.setTextColor(40, 45, 60);

      let x = margin;
      wrappedCells.forEach((lines, index) => {
        const column = columns[index];
        const textY = cursorY + cellPaddingY + 8;
        const textValue = lines.length > 0 ? lines : [DASH];

        if (column.align === 'right') {
          doc.text(textValue, x + column.width - cellPaddingX, textY, {
            align: 'right',
            baseline: 'top',
          });
        } else if (column.align === 'center') {
          doc.text(textValue, x + column.width / 2, textY, {
            align: 'center',
            baseline: 'top',
          });
        } else {
          doc.text(textValue, x + cellPaddingX, textY, { baseline: 'top' });
        }
        x += column.width;
      });

      cursorY += rowHeight;
    });

    cursorY += 12;
  };

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(20, 25, 38);
  doc.text('CrisisShield', margin, cursorY);
  cursorY += 18;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(13);
  doc.text(REPORT_TITLE, margin, cursorY);
  cursorY += 16;
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(70, 75, 92);
  doc.text(`Exported: ${formatDateTime(exportedAt)}`, margin, cursorY);
  cursorY += 12;
  doc.setDrawColor(200, 206, 218);
  doc.line(margin, cursorY, margin + contentWidth, cursorY);
  cursorY += 16;

  drawSectionTitle('Executive Summary');
  const summaryItems = [
    `Total Incidents: ${payload.stats.totalIncidents24h}`,
    `Active Alerts: ${payload.stats.activeAlerts}`,
    `Average Risk Score: ${payload.stats.avgRiskScore.toFixed(1)}`,
    `Highest-Risk Region: ${textCell(payload.stats.highestRiskRegion)}`,
  ];
  drawParagraph(summaryItems.join(' | '));

  drawSectionTitle('Active Alerts');
  const activeAlertsRows = sortByDateDesc(
    payload.alerts.filter((alert) => !alert.isAcknowledged),
    (alert) => alert.createdAt
  ).map((alert) => [
    textCell(alert.severity.toUpperCase()),
    textCell(alert.region),
    textCell(alert.title),
    formatDateTime(alert.createdAt),
  ]);
  drawTable(
    [
      { header: 'Severity', width: 70 },
      { header: 'Region', width: 100 },
      { header: 'Title', width: 290 },
      { header: 'Created', width: 95 },
    ],
    activeAlertsRows
  );

  drawSectionTitle('Recent Incidents');
  const incidentRows = sortByDateDesc(payload.recentIncidents, (incident) => incident.createdAt)
    .slice(0, 12)
    .map((incident) => [
      textCell(incident.severity.toUpperCase()),
      textCell(incident.region),
      textCell(incident.title),
      String(Math.round(incident.riskScore)),
      formatDateTime(incident.createdAt),
    ]);
  drawTable(
    [
      { header: 'Severity', width: 68 },
      { header: 'Region', width: 86 },
      { header: 'Incident', width: 235 },
      { header: 'Risk', width: 45, align: 'right' },
      { header: 'Timestamp', width: 121 },
    ],
    incidentRows
  );

  drawSectionTitle('Official Feed Highlights');
  const feedRows = sortByDateDesc(payload.officialFeedHighlights, (post) => post.publishedAt)
    .slice(0, 10)
    .map((post) => [
      textCell(post.publisherName),
      textCell(post.accountHandle ? `@${post.accountHandle}` : post.accountLabel),
      textCell(post.content),
      formatDateTime(post.publishedAt),
    ]);
  drawTable(
    [
      { header: 'Source', width: 120 },
      { header: 'Account', width: 92 },
      { header: 'Highlight', width: 270 },
      { header: 'Published', width: 73 },
    ],
    feedRows
  );

  drawSectionTitle('Regional Risk Summary');
  const riskRows = [...payload.riskScores]
    .sort((left, right) => right.overallScore - left.overallScore)
    .map((risk) => [
      textCell(risk.region),
      String(Math.round(risk.overallScore)),
      `${Math.round(risk.confidence * 100)}%`,
      formatDateTime(risk.calculatedAt),
    ]);
  drawTable(
    [
      { header: 'Region', width: 200 },
      { header: 'Risk Score', width: 90, align: 'right' },
      { header: 'Confidence', width: 90, align: 'right' },
      { header: 'Calculated', width: 180 },
    ],
    riskRows
  );

  const totalPages = doc.getNumberOfPages();
  console.log('TOTAL PAGES', totalPages);
  for (let page = 1; page <= totalPages; page += 1) {
    doc.setPage(page);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(120, 125, 140);
    doc.text(`Page ${page} of ${totalPages}`, pageWidth - margin, pageHeight - 14, { align: 'right' });
  }

  const filename = `CrisisShield-Situation-Overview-${formatFilenameTimestamp(exportedAt)}.pdf`;
  console.log('ABOUT TO SAVE PDF', filename);
  doc.save(filename);
  console.log('PDF SAVE CALLED');
}

