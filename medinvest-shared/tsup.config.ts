import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    'types/index': 'src/types/index.ts',
    'validators/index': 'src/validators/index.ts',
    'utils/index': 'src/utils/index.ts',
    'api/index': 'src/api/index.ts',
    'constants/index': 'src/constants/index.ts',
  },
  format: ['cjs', 'esm'],
  dts: true,
  splitting: false,
  sourcemap: true,
  clean: true,
  treeshake: true,
});
