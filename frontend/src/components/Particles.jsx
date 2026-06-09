import React, { useEffect, useRef } from 'react';

export function Particles({ enabled }) {
  const canvasRef = useRef(null);
  const animationFrameId = useRef(null);
  const particlesRef = useRef([]);
  const mouseRef = useRef({ x: null, y: null, radius: 110 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    class Particle {
      constructor() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.size = Math.random() * 2.5 + 0.5;
        this.speedX = Math.random() * 0.4 - 0.2;
        this.speedY = Math.random() * 0.4 - 0.2;
        this.color = Math.random() > 0.55 ? 'rgba(200, 155, 60, 0.22)' : 'rgba(10, 200, 185, 0.22)';
      }

      update() {
        this.x += this.speedX;
        this.y += this.speedY;

        if (this.x < 0) this.x = canvas.width;
        if (this.x > canvas.width) this.x = 0;
        if (this.y < 0) this.y = canvas.height;
        if (this.y > canvas.height) this.y = 0;

        if (mouseRef.current.x && mouseRef.current.y) {
          let dx = mouseRef.current.x - this.x;
          let dy = mouseRef.current.y - this.y;
          let dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < mouseRef.current.radius) {
            const force = (mouseRef.current.radius - dist) / mouseRef.current.radius;
            const dirX = dx / dist;
            const dirY = dy / dist;

            if (this.color.includes('200')) {
              this.x += dirX * force * 1.5;
              this.y += dirY * force * 1.5;
            } else {
              this.x -= dirX * force * 1.5;
              this.y -= dirY * force * 1.5;
            }
          }
        }
      }

      draw() {
        ctx.fillStyle = this.color;
        ctx.shadowBlur = this.size * 2;
        ctx.shadowColor = this.color.includes('200') ? 'rgba(200, 155, 60, 0.4)' : 'rgba(10, 200, 185, 0.4)';

        ctx.beginPath();
        ctx.moveTo(this.x, this.y - this.size);
        ctx.lineTo(this.x + this.size, this.y);
        ctx.lineTo(this.x, this.y + this.size);
        ctx.lineTo(this.x - this.size, this.y);
        ctx.closePath();
        ctx.fill();

        ctx.shadowBlur = 0;
      }
    }

    const initParticles = () => {
      resizeCanvas();
      const pCount = Math.floor((canvas.width * canvas.height) / 13000);
      particlesRef.current = [];
      for (let i = 0; i < Math.min(pCount, 120); i++) {
        particlesRef.current.push(new Particle());
      }
    };

    const animate = () => {
      if (!enabled) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        return;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particlesRef.current.forEach(p => {
        p.update();
        p.draw();
      });

      animationFrameId.current = requestAnimationFrame(animate);
    };

    const handleMouseMove = (e) => {
      mouseRef.current.x = e.clientX;
      mouseRef.current.y = e.clientY;
    };
    const handleMouseLeave = () => {
      mouseRef.current.x = null;
      mouseRef.current.y = null;
    };

    if (enabled) {
      initParticles();
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseleave', handleMouseLeave);
      window.addEventListener('resize', resizeCanvas);
      animate();
    } else {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (animationFrameId.current) cancelAnimationFrame(animationFrameId.current);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
      window.removeEventListener('resize', resizeCanvas);
      if (animationFrameId.current) cancelAnimationFrame(animationFrameId.current);
    };
  }, [enabled]);

  return <canvas id="particles-canvas" ref={canvasRef}></canvas>;
}
