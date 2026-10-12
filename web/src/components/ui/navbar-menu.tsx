import {
  useState,
  type AnchorHTMLAttributes,
  type ReactElement,
  type ReactNode,
} from "react";
import { motion, type Transition } from "motion/react";
import { FaBars, FaTimes } from 'react-icons/fa';
import { Link } from "react-router-dom";

const transition: Transition = {
  type: "spring",
  mass: 0.5,
  damping: 11.5,
  stiffness: 100,
  restDelta: 0.001,
  restSpeed: 0.001,
};

export interface MenuItemProps {
  setActive: (item: string | null) => void;
  active: string | null;
  item: string;
  children?: ReactNode;
}

export const MenuItem = ({
  setActive,
  active,
  item,
  children
}: MenuItemProps) => {
  return (
    <div onMouseEnter={() => setActive(item)} className="relative">
      <motion.p
        transition={{ duration: 0.3 }}
        className="cursor-pointer text-black hover:opacity-[0.9] dark:text-white px-3 py-2 rounded-md text-sm font-medium whitespace-nowrap">
        {item}
      </motion.p>
      {active !== null && (
        <motion.div
          initial={{ opacity: 0, scale: 0.85, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={transition}>
          {active === item && (
            <div className="absolute top-[calc(100%_+_0.5rem)] left-1/2 transform -translate-x-1/2 pt-4">
              <motion.div
                transition={transition}
                layoutId={`active-menu-item-${item}`}
                className="bg-white dark:bg-black backdrop-blur-sm rounded-2xl overflow-hidden border border-black/[0.2] dark:border-white/[0.2] shadow-xl">
                <motion.div layout className="w-max h-full p-4">
                  {children}
                </motion.div>
              </motion.div>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
};

// One entry of the menu that opens on small screens, where the center slot is hidden
export interface MobileLink {
  name: string;
  // A path of this app
  to: string;
  // Opens the page in a new tab
  newTab?: boolean;
}

export interface MenuProps {
  setActive: (item: string | null) => void;
  // Three slots: left, center and right
  children: ReactElement[];
  mobileLinks: MobileLink[];
}

export const Menu = ({
  setActive,
  children,
  mobileLinks
}: MenuProps) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <>
      <nav
        onMouseLeave={() => {
          setActive(null);
        }}
        className="fixed top-4 left-1/2 transform -translate-x-1/2 w-[98vw] max-w-9xl z-50 rounded-full border border-transparent dark:border-white/[0.2] bg-white/80 dark:bg-black/80 backdrop-blur-md shadow-input flex items-center justify-between px-8 py-4"
      >
        {/* Left section: org logo/name (children[0]) */}
        <div className="flex items-center min-w-0">{children[0]}</div>
        {/* Center section: menu items (children[1]) */}
        <div className="hidden md:flex items-center justify-center flex-1 space-x-6 lg:space-x-8 mx-8 min-w-0">{children[1]}</div>
        {/* Right section: org switcher/logout (children[2]) */}
        <div className="flex items-center min-w-0">{children[2]}</div>
        {/* Mobile menu toggle */}
        <div className="md:hidden flex-shrink-0">
          <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="cursor-pointer text-black dark:text-white hover:opacity-80 transition-opacity duration-200">
            {isMobileMenuOpen ? <FaTimes size={24} /> : <FaBars size={24} />}
          </button>
        </div>
      </nav>

      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <div className="md:hidden fixed inset-0 top-16 overflow-y-auto bg-white/90 dark:bg-black/90 backdrop-blur-lg z-40 pt-10">
          <ul className="flex flex-col items-center space-y-4 p-4">
            {mobileLinks.map((link) => (
              <li key={link.name} className="w-full text-center">
                <Link
                  to={link.to}
                  {...(link.newTab ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                  onClick={() => setIsMobileMenuOpen(false)} // Close menu on link click
                  className="cursor-pointer text-lg text-neutral-700 dark:text-neutral-200 hover:text-soda-blue dark:hover:text-soda-blue py-3 block w-full rounded-md transition-colors duration-200"
                >
                  {link.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
};

export interface ProductItemProps {
  title: string;
  description: string;
  href: string;
  src: string;
}

export const ProductItem = ({
  title,
  description,
  href,
  src
}: ProductItemProps) => {
  return (
    <a href={href} className="flex space-x-2">
      <img
        src={src}
        width={140}
        height={70}
        alt={title}
        className="flex-shrink-0 rounded-md shadow-2xl" />
      <div>
        <h4 className="text-xl font-bold mb-1 text-black dark:text-white">
          {title}
        </h4>
        <p className="text-neutral-700 text-sm max-w-[10rem] dark:text-neutral-300">
          {description}
        </p>
      </div>
    </a>
  );
};

export type HoveredLinkProps = AnchorHTMLAttributes<HTMLAnchorElement>;

export const HoveredLink = ({
  children,
  ...rest
}: HoveredLinkProps) => {
  return (
    <a {...rest} className="cursor-pointer text-neutral-700 dark:text-neutral-200 hover:text-black dark:hover:text-soda-blue p-2 rounded-md transition-colors duration-200">
      {children}
    </a>
  );
};