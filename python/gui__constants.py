from PySide6.QtCore import QSize

class Colors:
    class Light:
        on = "#6f3"
        off = "#888"

    class Segment:
        on = "#ff5f6d"
        off = "#fff"
        background = "#ccc"

    class Button:
        class Light:
            pen = "#000"
            on_fill = "#aab"
            off_fill = "#eee"
            focus = "#0082e6"
        class Dark:
            pen ="#fff"
            on_fill = "#556"
            off_fill = "#333"
            focus = "#90cfff"
    
    class Switch:
        class Light:
            bg_fill = "#eee"
            pen = "#000"
            on_fill = "#cce"
            off_fill = "#aaa"
        class Dark:
            bg_fill = "#222"
            pen = "#fff"
            on_fill = "#99b"
            off_fill = "#333"

    class DotMatrix:
        on = "#ffc145"
        off = "#7d5300"
        background = "#111"


class Sizes:
    light = QSize(14, 14)
    mini_dotmatrix_light = QSize(10, 10)
    switch = QSize(14, 28)

    base_light_size = 10
    dp_margin = 8
    dp = QSize(base_light_size, base_light_size)
    horz_light = QSize(base_light_size * 3, base_light_size)
    vert_light = QSize(base_light_size, base_light_size * 3)

    calc_button_height = 50
    calc_button_font = 30


light_off_time = 100
light_fade_delay_time = 0
segment_off_time = 100
segment_fade_delay_time = 65