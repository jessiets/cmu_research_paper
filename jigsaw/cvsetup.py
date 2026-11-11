"""Import OpenCV through this module so its thread count is always 1."""

import cv2

cv2.setNumThreads(1)

__all__ = ["cv2"]
