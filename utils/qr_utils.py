import qrcode
import io
import base64


def generate_qr_base64(did: str, base_url: str = "http://localhost:5000") -> str:
    """
    Generates a QR code PNG (base64-encoded) that points to:
        <base_url>/verify?did=<did>

    Returns a data URI string ready to drop into an <img src="..."> tag.
    """
    url = f"{base_url}/verify?did={did}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    b64 = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{b64}"
