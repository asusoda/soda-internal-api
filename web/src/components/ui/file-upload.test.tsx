import { render } from '@testing-library/react';
import { expect, test } from 'vitest';
import { FileUpload } from './file-upload';

test('the file picker takes only the accepted types', () => {
  const { container } = render(<FileUpload accept={{ 'text/csv': ['.csv'] }} />);
  expect(container.querySelector('input[type="file"]')?.getAttribute('accept')).toBe('text/csv,.csv');
});
