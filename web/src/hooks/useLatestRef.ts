import { useEffect, useRef } from 'react';

// Returns a ref that holds the value from the latest render. An effect that must
// run only once, or only when one value changes, can call the latest version of a
// function through this ref without listing the function as a dependency.
const useLatestRef = <T>(value: T) => {
  const ref = useRef(value);
  useEffect(() => {
    ref.current = value;
  });
  return ref;
};

export default useLatestRef;
