import cv2
im = cv2.imread("out/stills/still_058.80.png")
c = im[780:950, 600:1330]
c = cv2.resize(c, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC)
cv2.imwrite("out/stills/ev_cta_zoom.png", c)
print(c.shape)
