import base64
import mimetypes
import os


def build_logo_src(business, request):
    if not business or not getattr(business, "logo", None):
        return ""
    try:
        logo_path = business.logo.path
    except Exception:
        logo_path = None
    if logo_path and os.path.exists(logo_path):
        mime_type, _ = mimetypes.guess_type(logo_path)
        mime_type = mime_type or "image/png"
        with open(logo_path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
    try:
        return request.build_absolute_uri(business.logo.url)
    except Exception:
        return ""
