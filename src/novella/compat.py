
def removesuffix(s: str, suffix: str) -> str:
  if s.endswith(suffix):
    s = s[:-len(suffix)]
  return s
