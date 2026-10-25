import cv2
def crop(src, box, scale, dst):
    im = cv2.imread(f"out/stills/{src}")
    x0,y0,x1,y1 = box
    c = im[y0:y1, x0:x1]
    c = cv2.resize(c, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(f"out/stills/{dst}", c)
    print(dst, c.shape)

crop("still_016.00.png", (30, 130, 800, 300), 2.2, "ev_s3_label_collision.png")
crop("still_035.50.png", (600, 420, 1250, 530), 2.4, "ev_s4_toast_occludes_row1.png")
crop("still_051.60.png", (300, 150, 1620, 460), 1.2, "ev_end_glow_rect_band.png")
crop("still_046.00.png", (640, 360, 1560, 900), 1.5, "ev_pdf_dup_rows.png")
crop("still_006.60.png", (100, 90, 800, 560), 1.6, "ev_s1_counter.png")
crop("still_055.30.png", (600, 760, 1350, 950), 2.4, "ev_cta_zoom.png")
