import io
import base64
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, KeepTogether
from reportlab.pdfgen import canvas
from PIL import Image as PILImage

class NumberedCanvas(canvas.Canvas):
    """
    Custom canvas to calculate total page count dynamically
    and draw professional headers and footers on each page.
    """
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Draw Header (skip page 1)
        if self._pageNumber > 1:
            self.drawString(inch, 10.4 * inch, "E2B Sandbox Analysis Report")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(inch, 10.3 * inch, 7.5 * inch, 10.3 * inch)
            
        # Draw Footer (all pages)
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(7.5 * inch, 0.45 * inch, page_text)
        self.drawString(inch, 0.45 * inch, "Generated via Streamlit E2B Coding Agent Sandbox")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(inch, 0.58 * inch, 7.5 * inch, 0.58 * inch)
        
        self.restoreState()

def format_text_for_pdf(text):
    """
    Helper to escape XML entities and convert line breaks to paragraph breaks or line breaks.
    """
    if not text:
        return ""
    escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return escaped.replace('\n', '<br/>')

def format_code_for_pdf(code):
    """
    Helper to format code while preserving syntax indentation and spacing.
    """
    if not code:
        return ""
    escaped = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    formatted_lines = []
    for line in escaped.splitlines():
        leading_spaces = len(line) - len(line.lstrip(' '))
        # Replace leading spaces with non-breaking space characters
        nbsp_str = '&nbsp;' * leading_spaces
        formatted_lines.append(nbsp_str + line.lstrip(' '))
    return '<br/>'.join(formatted_lines)

def generate_pdf_report(query, text_response, code_executed, console_output, base64_charts, doc_name, doc_size_str):
    """
    Compiles a comprehensive PDF report containing the original query, model commentary,
    the code block ran, E2B environment output, and any charts generated.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=inch,
        rightMargin=inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette and Typography
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=8
    )
    
    subtitle_style = ParagraphStyle(
        'ReportSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=20
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#334155'),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=8
    )
    
    code_style = ParagraphStyle(
        'ReportCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#0F172A'),
        backColor=colors.HexColor('#F8FAFC'),
        borderColor=colors.HexColor('#E2E8F0'),
        borderWidth=0.5,
        borderPadding=8,
        spaceAfter=10
    )

    log_style = ParagraphStyle(
        'ReportLogs',
        parent=code_style,
        textColor=colors.HexColor('#475569'),
        backColor=colors.HexColor('#F1F5F9'),
        borderColor=colors.HexColor('#E2E8F0')
    )
    
    story = []
    
    # 1. Title and Document Metadata
    story.append(Paragraph("E2B Sandbox Analysis Report", title_style))
    meta_info = f"<b>Document:</b> {doc_name} ({doc_size_str}) &nbsp;&nbsp;|&nbsp;&nbsp; <b>Query:</b> {format_text_for_pdf(query)}"
    story.append(Paragraph(meta_info, subtitle_style))
    story.append(Spacer(1, 8))
    
    # 2. Executive Summary / Text Response
    story.append(Paragraph("Executive Summary", h1_style))
    story.append(Paragraph(format_text_for_pdf(text_response), body_style))
    story.append(Spacer(1, 10))
    
    # 3. Python Analysis Code
    if code_executed:
        story.append(Paragraph("Python Analysis Code", h1_style))
        story.append(Paragraph(format_code_for_pdf(code_executed), code_style))
        story.append(Spacer(1, 10))
        
    # 4. Execution Output / Logs
    if console_output:
        story.append(Paragraph("Sandbox Console Output", h1_style))
        story.append(Paragraph(format_code_for_pdf(console_output), log_style))
        story.append(Spacer(1, 10))
        
    # 5. Visualizations
    if base64_charts:
        story.append(Paragraph("Data Visualizations", h1_style))
        for idx, chart_b64 in enumerate(base64_charts):
            try:
                img_data = base64.b64decode(chart_b64)
                img_io = io.BytesIO(img_data)
                
                # Check dimensions with PIL
                pil_img = PILImage.open(img_io)
                w, h = pil_img.size
                
                # Scale image to fit page width
                max_width = 5.5 * inch
                scale = max_width / w if w > max_width else 1.0
                target_w = w * scale
                target_h = h * scale
                
                img_io.seek(0)
                img_flowable = Image(img_io, width=target_w, height=target_h)
                
                chart_block = [
                    Paragraph(f"Figure {idx + 1}: Generated Visualization", h2_style),
                    Spacer(1, 4),
                    img_flowable,
                    Spacer(1, 12)
                ]
                story.append(KeepTogether(chart_block))
            except Exception as e:
                story.append(Paragraph(f"<i>Error rendering chart {idx + 1}: {format_text_for_pdf(str(e))}</i>", body_style))
                story.append(Spacer(1, 8))
                
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
