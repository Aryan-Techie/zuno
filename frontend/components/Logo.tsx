/**
 * The Zuno mark.
 *
 * Inlined rather than loaded as a file so it inherits the theme without a
 * second request or a flash of the wrong ink. The two body paths take
 * `--logo-ink`, which flips with the theme in globals.css; the blue is a
 * constant and stays put, so the mark keeps its identity on either ground.
 *
 * Path data is generated from dark.svg — regenerate rather than hand-edit.
 */
export function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg
      className="mark"
      width={size}
      height={(size * 1079) / 1313}
      viewBox="0 0 1313 1079"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M188.2 57.71C232.82 20.43 289.12 0 347.26 0L1208 0C1265.99 0 1313 47.01 1313 105L1313 160C1313 190.38 1288.38 215 1258 215L45 215C29.74 215 22.82 195.93 34.53 186.14L188.2 57.71Z" fill="var(--logo-ink)" />
      <path d="M1124.8 1021.29C1080.18 1058.57 1023.88 1079 965.74 1079L105 1079C47.01 1079 0 1031.99 0 974L0 919C0 888.62 24.62 864 55 864L1268 864C1283.26 864 1290.18 883.07 1278.47 892.86L1124.8 1021.29Z" fill="var(--logo-ink)" />
      <path d="M716.99 298.56C774.74 266.55 840.97 255 907 255L1265 255C1274.53 255 1277.23 267.98 1268.62 272.05C997.06 400.56 852.06 638.52 596.01 780.44C538.26 812.45 472.03 824 406 824L48 824C38.47 824 35.77 811.02 44.38 806.95C315.94 678.44 460.94 440.48 716.99 298.56Z" fill="var(--logo-accent)" />
    </svg>
  );
}
