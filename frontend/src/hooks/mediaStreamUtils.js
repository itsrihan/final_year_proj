export function stopMediaStream(stream) {
  if (!stream) {
    return;
  }

  stream.getTracks().forEach((track) => {
    track.stop();
    track.enabled = false;
  });
}

export function detachVideoElement(videoElement) {
  if (!videoElement) {
    return;
  }

  videoElement.pause();
  videoElement.srcObject = null;
  videoElement.removeAttribute("srcObject");
  videoElement.load();
}

export function attachVideoElement(videoElement, stream) {
  if (!videoElement) {
    return;
  }

  videoElement.srcObject = stream ?? null;
}
