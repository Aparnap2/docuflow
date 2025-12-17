"""
Compression utility for Docuflow
Handles image compression and PDF optimization
"""
import os
from typing import Optional, Tuple
from loguru import logger
from PIL import Image
import pikepdf
from io import BytesIO


class CompressionUtility:
    """
    Compression utility class for optimizing documents
    """
    
    @staticmethod
    def compress_image(input_path: str, output_path: str, quality: int = 85) -> bool:
        """
        Compress an image file
        :param input_path: Path to input image
        :param output_path: Path to output image
        :param quality: JPEG quality (1-100)
        :return: True if compression was successful
        """
        try:
            with Image.open(input_path) as img:
                # Convert to RGB if necessary (for JPEG)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # Save with specified quality
                img.save(output_path, "JPEG", quality=quality, optimize=True)
                
                original_size = os.path.getsize(input_path)
                compressed_size = os.path.getsize(output_path)
                
                logger.info(f"Compressed image from {original_size} to {compressed_size} bytes "
                           f"({(1 - compressed_size/original_size)*100:.1f}% reduction)")
                
                return True
        except Exception as e:
            logger.error(f"Error compressing image {input_path}: {e}")
            return False
    
    @staticmethod
    def compress_image_from_bytes(image_bytes: bytes, quality: int = 85) -> Optional[bytes]:
        """
        Compress image from bytes
        :param image_bytes: Input image as bytes
        :param quality: JPEG quality (1-100)
        :return: Compressed image as bytes or None if failed
        """
        try:
            with Image.open(BytesIO(image_bytes)) as img:
                # Convert to RGB if necessary (for JPEG)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                output_buffer = BytesIO()
                img.save(output_buffer, "JPEG", quality=quality, optimize=True)
                
                compressed_bytes = output_buffer.getvalue()
                
                logger.info(f"Compressed image from {len(image_bytes)} to {len(compressed_bytes)} bytes "
                           f"({(1 - len(compressed_bytes)/len(image_bytes))*100:.1f}% reduction)")
                
                return compressed_bytes
        except Exception as e:
            logger.error(f"Error compressing image from bytes: {e}")
            return None
    
    @staticmethod
    def compress_pdf(input_path: str, output_path: str) -> bool:
        """
        Compress a PDF file using pikepdf
        :param input_path: Path to input PDF
        :param output_path: Path to output PDF
        :return: True if compression was successful
        """
        try:
            original_size = os.path.getsize(input_path)
            
            # Open and optimize the PDF
            pdf = pikepdf.Pdf.open(input_path)
            
            # Optimize the PDF
            pdf.save(output_path, 
                    compress_streams=True,
                    stream_decode_level=pikepdf.StreamDecodeLevel.all,
                    normalize_content=True,
                    fix_metadata_version=True)
            
            compressed_size = os.path.getsize(output_path)
            
            logger.info(f"Compressed PDF from {original_size} to {compressed_size} bytes "
                       f"({(1 - compressed_size/original_size)*100:.1f}% reduction)")
            
            return True
        except Exception as e:
            logger.error(f"Error compressing PDF {input_path}: {e}")
            return False
    
    @staticmethod
    def compress_pdf_from_bytes(pdf_bytes: bytes) -> Optional[bytes]:
        """
        Compress PDF from bytes
        :param pdf_bytes: Input PDF as bytes
        :return: Compressed PDF as bytes or None if failed
        """
        try:
            original_size = len(pdf_bytes)
            
            # Create input and output buffers
            input_buffer = BytesIO(pdf_bytes)
            
            # Open and optimize the PDF
            pdf = pikepdf.Pdf.open(input_buffer)
            
            # Create output buffer
            output_buffer = BytesIO()
            
            # Optimize the PDF
            pdf.save(output_buffer,
                    compress_streams=True,
                    stream_decode_level=pikepdf.StreamDecodeLevel.all,
                    normalize_content=True,
                    fix_metadata_version=True)
            
            compressed_bytes = output_buffer.getvalue()
            
            logger.info(f"Compressed PDF from {original_size} to {compressed_bytes} bytes "
                       f"({(1 - len(compressed_bytes)/original_size)*100:.1f}% reduction)")
            
            return compressed_bytes
        except Exception as e:
            logger.error(f"Error compressing PDF from bytes: {e}")
            return None
    
    @staticmethod
    def convert_images_to_pdf(image_paths: list, output_path: str) -> bool:
        """
        Convert a list of image files to a single PDF
        :param image_paths: List of image file paths
        :param output_path: Path to output PDF
        :return: True if conversion was successful
        """
        try:
            images = []
            for path in image_paths:
                with Image.open(path) as img:
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    images.append(img.copy())
            
            if images:
                # Save first image and append the rest
                images[0].save(output_path, "PDF", resolution=100.0, save_all=True, append_images=images[1:])
                logger.info(f"Converted {len(image_paths)} images to PDF: {output_path}")
                return True
            else:
                logger.error("No images provided for PDF conversion")
                return False
        except Exception as e:
            logger.error(f"Error converting images to PDF: {e}")
            return False
    
    @staticmethod
    def convert_images_bytes_to_pdf(images_bytes: list) -> Optional[bytes]:
        """
        Convert a list of image bytes to a single PDF
        :param images_bytes: List of image bytes
        :return: PDF as bytes or None if failed
        """
        try:
            images = []
            for img_bytes in images_bytes:
                with Image.open(BytesIO(img_bytes)) as img:
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    images.append(img.copy())
            
            if images:
                output_buffer = BytesIO()
                # Save first image and append the rest
                images[0].save(output_buffer, "PDF", resolution=100.0, save_all=True, append_images=images[1:])
                
                pdf_bytes = output_buffer.getvalue()
                logger.info(f"Converted {len(images_bytes)} images to PDF ({len(pdf_bytes)} bytes)")
                
                return pdf_bytes
            else:
                logger.error("No images provided for PDF conversion")
                return None
        except Exception as e:
            logger.error(f"Error converting images bytes to PDF: {e}")
            return None