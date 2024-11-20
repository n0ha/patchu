from flask import Flask, request, send_file, render_template
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageOps
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from io import BytesIO
import math
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Constants
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
DPI = 150  # Reduced DPI to reduce file size while maintaining print quality
A4_WIDTH_PX = int(A4_WIDTH_MM / 25.4 * DPI)
A4_HEIGHT_PX = int(A4_HEIGHT_MM / 25.4 * DPI)
MAX_IMAGE_SIZE_MB = 10  # Limit input image size to 10 MB
MAX_TARGET_HEIGHT_CM = 300  # Limit target height to 300 cm


def scale_and_slice_image_in_memory(image, target_height_cm):
    start_time = time.time()
    image_width, image_height = image.size
    logger.info(f"Original image size: width={image_width}px, height={image_height}px")

    # Calculate scaling factor
    target_height_px = int(target_height_cm / 2.54 * DPI)
    scaling_factor = target_height_px / image_height
    target_width_px = int(image_width * scaling_factor)
    logger.info(f"Scaling factor: {scaling_factor:.2f}, Target size: width={target_width_px}px, height={target_height_px}px")

    # Scale the image
    scaled_image = image.resize((target_width_px, target_height_px), Image.Resampling.LANCZOS)
    logger.info(f"Scaled image size: width={scaled_image.width}px, height={scaled_image.height}px")

    # Convert to RGB if not already (for JPEG format)
    if scaled_image.mode != "RGB":
        scaled_image = scaled_image.convert("RGB")
        logger.info("Image converted to RGB mode for JPEG compatibility.")

    # Calculate number of A4 pages needed
    rows = math.ceil(target_height_px / A4_HEIGHT_PX)
    cols = math.ceil(target_width_px / A4_WIDTH_PX)
    logger.info(f"Number of pages needed: rows={rows}, cols={cols}")

    # Create a PDF in-memory
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer, pagesize=A4)

    # Slice the image and add to PDF
    for row in range(rows):
        for col in range(cols):
            # Calculate crop box
            left = col * A4_WIDTH_PX
            upper = row * A4_HEIGHT_PX
            right = min((col + 1) * A4_WIDTH_PX, target_width_px)
            lower = min((row + 1) * A4_HEIGHT_PX, target_height_px)
            logger.info(f"Cropping image: row={row + 1}, col={col + 1}, box=({left}, {upper}, {right}, {lower})")

            # Crop the image
            cropped_image = scaled_image.crop((left, upper, right, lower))

            # Save the cropped image to an in-memory buffer with JPEG compression
            cropped_buffer = BytesIO()
            cropped_image.save(cropped_buffer, format="JPEG", quality=85)  # Use JPEG with quality setting to reduce size
            cropped_buffer.seek(0)

            # Use ImageReader to handle BytesIO
            img = ImageReader(cropped_buffer)

            # Draw the image on the PDF to fit the entire A4 page
            pdf.drawImage(img, 0, 0, width=A4_WIDTH_MM * 72 / 25.4, height=A4_HEIGHT_MM * 72 / 25.4)

            # Add hints for stitching pages together with a contrast background
            pdf.setFillColorRGB(1, 1, 1)  # White background for contrast
            pdf.rect(8, 8, 300, 15, fill=1)  # Draw a filled rectangle for contrast
            pdf.setFillColorRGB(0, 0, 0)  # Black text color
            pdf.setFont("Helvetica", 8)
            hint_text = f"Row {row + 1} of {rows}, Column {col + 1} of {cols}. Align edges with adjacent pages."
            pdf.drawString(10, 10, hint_text)

            cropped_buffer.close()
            pdf.showPage()

    # Finalize PDF
    pdf.save()
    pdf_buffer.seek(0)
    end_time = time.time()
    logger.info(f"PDF generation complete. Time taken: {end_time - start_time:.2f} seconds.")
    return pdf_buffer


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Get uploaded file and target height
        file = request.files.get("image")
        target_height_cm = float(request.form.get("target_height"))

        if file:
            # Check file size limit
            file.seek(0, 2)  # Move the cursor to the end of the file
            file_size_mb = file.tell() / (1024 * 1024)
            file.seek(0)  # Move the cursor back to the beginning
            if file_size_mb > MAX_IMAGE_SIZE_MB:
                logger.warning(f"File size exceeds limit: {file_size_mb:.2f} MB (max {MAX_IMAGE_SIZE_MB} MB)")
                return "File size exceeds the maximum limit of 10 MB.", 400

            # Check target height limit
            if target_height_cm > MAX_TARGET_HEIGHT_CM:
                logger.warning(f"Target height exceeds limit: {target_height_cm} cm (max {MAX_TARGET_HEIGHT_CM} cm)")
                return "Target height exceeds the maximum limit of 300 cm.", 400

            logger.info(f"Received file: {file.filename}, Target height: {target_height_cm} cm")
            # Open the uploaded image
            image = Image.open(file.stream)

            # Process and generate PDF
            pdf_buffer = scale_and_slice_image_in_memory(image, target_height_cm)

            # Return PDF as download
            logger.info("Sending generated PDF to client.")
            return send_file(
                pdf_buffer,
                as_attachment=True,
                download_name="blueprint.pdf",
                mimetype="application/pdf"
            )

    return render_template("index.html")


# Run the app
if __name__ == "__main__":
    logger.info("Starting Flask server...")
    app.run(host="0.0.0.0", port=5000)
