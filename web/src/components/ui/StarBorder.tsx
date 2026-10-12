import type { ButtonHTMLAttributes, ReactNode } from 'react';

// A button with stars that move along its border
export interface StarBorderProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'color'> {
  className?: string;
  color?: string;
  speed?: string;
  children?: ReactNode;
}

const StarBorder = ({
  className = "",
  color = "#007AFF",
  speed = "6s",
  children,
  ...rest
}: StarBorderProps) => {
  return (
    <button className={`relative inline-block py-[1px] overflow-hidden rounded-[20px] ${className}`} {...rest}>
      <div
        className="absolute w-[300%] h-[50%] opacity-50 bottom-[-11px] right-[-250%] rounded-full animate-star-movement-bottom z-0"
        style={{
          background: `radial-gradient(circle, ${color}, transparent 20%)`,
          animationDuration: speed,
        }}
      ></div>
      <div
        className="absolute w-[300%] h-[50%] opacity-50 top-[-10px] left-[-250%] rounded-full animate-star-movement-top z-0"
        style={{
          background: `radial-gradient(circle, ${color}, transparent 20%)`,
          animationDuration: speed,
        }}
      ></div>
      <div className="relative z-1 bg-soda-black border border-soda-gray text-soda-white text-center text-[16px] py-[16px] px-[26px] rounded-[20px]">
        {children}
      </div>
    </button>
  );
};

export default StarBorder; 