import { fireEvent, render, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { FileUpload } from './file-upload';

const renderUpload = (onChange = vi.fn()) => {
  const { container } = render(<FileUpload accept={{ 'text/csv': ['.csv'] }} onChange={onChange} />);
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  return { input, onChange };
};

test('the file picker takes only the accepted types', () => {
  expect(renderUpload().input.getAttribute('accept')).toBe('text/csv,.csv');
});

test('a picked file of another type does not reach onChange', async () => {
  const { input, onChange } = renderUpload();
  const csv = new File(['a@asu.edu'], 'people.csv', { type: 'text/csv' });
  const image = new File(['x'], 'photo.png', { type: 'image/png' });

  fireEvent.change(input, { target: { files: [image] } });
  fireEvent.change(input, { target: { files: [csv] } });

  await waitFor(() => expect(onChange).toHaveBeenCalledTimes(1));
  expect(onChange).toHaveBeenCalledWith([csv]);
});
