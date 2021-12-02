from renderer.base import RendererBase


class Renderer(RendererBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._res_package = f"{__package__}.resources"
