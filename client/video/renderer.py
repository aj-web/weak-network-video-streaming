import cv2

class VideoRenderer:
    def __init__(self, window_title="Video"):
        self.window_title = window_title
        cv2.namedWindow(self.window_title, cv2.WINDOW_NORMAL)

    def render(self, frame):
        if frame is not None:
            cv2.imshow(self.window_title, frame)
            cv2.waitKey(1)

    def close(self):
        cv2.destroyAllWindows() 