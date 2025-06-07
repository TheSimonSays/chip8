import argparse
import pygame
import random
import sys
import time
from pygame import Surface, font


class Chip8:
    def __init__(self, debug: bool = False, cycles_per_frame: int = 10) -> None:
        self.memory: list[int] = [0] * 0x1000
        self.V: list[int] = [0] * 16
        self.I: int = 0
        self.PC: int = 0x200
        self.stack: list[int] = [0] * 16
        self.SP: int = 0
        self.delay_timer: int = 0
        self.sound_timer: int = 0
        self.display: list[int] = [[0] * 64 for _ in range(32)]
        self.fontset: list[int] = [
            0xF0, 0x90, 0x90, 0x90, 0xF0,
            0x20, 0x60, 0x20, 0x20, 0x70,
            0xF0, 0x10, 0xF0, 0x80, 0xF0,
            0xF0, 0x10, 0xF0, 0x10, 0xF0,
            0x90, 0x90, 0xF0, 0x10, 0x10,
            0xF0, 0x80, 0xF0, 0x10, 0xF0,
            0xF0, 0x80, 0xF0, 0x90, 0xF0,
            0xF0, 0x10, 0x20, 0x40, 0x40,
            0xF0, 0x90, 0xF0, 0x90, 0xF0,
            0xF0, 0x90, 0xF0, 0x10, 0xF0,
            0xF0, 0x90, 0xF0, 0x90, 0x90,
            0xE0, 0x90, 0xE0, 0x90, 0xE0,
            0xF0, 0x80, 0x80, 0x80, 0xF0,
            0xE0, 0x90, 0x90, 0x90, 0xE0,
            0xF0, 0x80, 0xF0, 0x80, 0xF0,
            0xF0, 0x80, 0xF0, 0x80, 0x80 
        ]

        for i, byte in enumerate(self.fontset):
            self.memory[0x050 + i] = byte

        self.keys: list[int] = [0] * 16
        self.debug: bool = debug
        self.cycles_per_frame: int = cycles_per_frame

        pygame.init()

        width: int = 640 + (200 if debug else 0)
        self.screen: Surface = pygame.display.set_mode((width, 320))

        pygame.display.set_caption("Shitty chip-8 emulator")

        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.debug_font: font.Font = pygame.font.SysFont("monospace", 14)

    def load_rom(self, rom_path: str) -> None:
        with open(rom_path, "rb") as f:
            rom: bytes = f.read()

        for i, byte in enumerate(rom):
            self.memory[0x200 + i] = byte
        print(f"Loaded ROM: {rom_path}, size={len(rom)} bytes")

    def clear_display(self) -> None:
        self.display = [[0] * 64 for _ in range(32)]

    def draw_sprite(self, x: int, y: int, height: int) -> int:
        collision: int = 0
        x_coord: int = self.V[x] & 0x3F
        y_coord: int = self.V[y] & 0x1F
        for row in range(height):
            sprite_byte: int = self.memory[self.I + row]
            for col in range(8):
                if sprite_byte & (0x80 >> col):
                    px: int = (x_coord + col) & 0x3F
                    py: int = (y_coord + row) & 0x1F
                    if self.display[py][px] == 1:
                        collision = 1
                    self.display[py][px] ^= 1
        return collision

    def update_display(self) -> None:
        self.screen.fill((0, 0, 0))
        for y in range(32):
            for x in range(64):
                if self.display[y][x]:
                    pygame.draw.rect(
                        self.screen, (255, 255, 255), (x * 10, y * 10, 10, 10)
                    )
    
        if self.debug:
            pygame.draw.rect(self.screen, (50, 50, 50), (640, 0, 200, 320))
            debug_lines: list[str] = [
                f"PC: {hex(self.PC)}",
                f"I:  {hex(self.I)}",
                f"SP: {self.SP}",
                "Registers:",
            ]
            for i in range(0, 16, 4):
                regs: str = " ".join(f"V{j:X}={hex(self.V[j])[-2:].upper()}" for j in range(i, min(i+4, 16)))
                debug_lines.append(regs)

            debug_lines.append("Stack:")
            stack_vals: str = " ".join(hex(self.stack[i])[-4:].upper() for i in range(self.SP))
            debug_lines.append(stack_vals if stack_vals else "Empty")

            debug_lines.append("Keys:")
            active_keys: str = " ".join(f"{i:X}" for i in range(16) if self.keys[i])
            debug_lines.append(active_keys if active_keys else "None")

            for i, line in enumerate(debug_lines):
                text: Surface = self.debug_font.render(line, True, (255, 255, 255))
                self.screen.blit(text, (650, 10 + i * 18))

        pygame.display.flip()

    def handle_input(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
        key_map: dict[int, int] = {
            pygame.K_1: 0x1, pygame.K_2: 0x2, pygame.K_3: 0x3, pygame.K_4: 0xC,
            pygame.K_q: 0x4, pygame.K_w: 0x5, pygame.K_e: 0x6, pygame.K_r: 0xD,
            pygame.K_a: 0x7, pygame.K_s: 0x8, pygame.K_d: 0x9, pygame.K_f: 0xE,
            pygame.K_z: 0xA, pygame.K_x: 0x0, pygame.K_c: 0xB, pygame.K_v: 0xF
        }
        keys: list[int] = pygame.key.get_pressed()

        for i in range(16):
            self.keys[i] = 0
        for key, chip8_key in key_map.items():
            if keys[key]:
                self.keys[chip8_key] = 1

    def emulate_cycle(self) -> None:
        opcode: int = (self.memory[self.PC] << 8) | self.memory[self.PC + 1]
        self.PC += 2
        # trying to decode this shit
        x: int = (opcode & 0x0F00) >> 8
        y: int = (opcode & 0x00F0) >> 4
        n: int = opcode & 0x000F
        nn: int = opcode & 0x00FF
        nnn: int = opcode & 0x0FFF

        # alright, let's execute this shit
        if opcode == 0x00E0:
            self.clear_display()
        elif opcode == 0x00EE:
            self.SP -= 1
            self.PC = self.stack[self.SP]
        elif (opcode & 0xF000) == 0x1000:
            self.PC = nnn
        elif (opcode & 0xF000) == 0x2000:
            self.stack[self.SP] = self.PC
            self.SP += 1
            self.PC = nnn
        elif (opcode & 0xF000) == 0x3000:
            if self.V[x] == nn:
                self.PC += 2
        elif (opcode & 0xF000) == 0x4000:
            if self.V[x] != nn:
                self.PC += 2
        elif (opcode & 0xF000) == 0x5000 and (opcode & 0x000F) == 0:
            if self.V[x] == self.V[y]:
                self.PC += 2
        elif (opcode & 0xF000) == 0x6000:
            self.V[x] = nn
        elif (opcode & 0xF000) == 0x7000:
            self.V[x] = (self.V[x] + nn) & 0xFF
        elif (opcode & 0xF00F) == 0x8000:
            self.V[x] = self.V[y]
        elif (opcode & 0xF00F) == 0x8001:
            self.V[x] |= self.V[y]
        elif (opcode & 0xF00F) == 0x8002:
            self.V[x] &= self.V[y]
        elif (opcode & 0xF00F) == 0x8003:
            self.V[x] ^= self.V[y]
        elif (opcode & 0xF00F) == 0x8004:
            result = self.V[x] + self.V[y]
            self.V[0xF] = 1 if result > 0xFF else 0
            self.V[x] = result & 0xFF
        elif (opcode & 0xF00F) == 0x8005:
            self.V[0xF] = 1 if self.V[x] >= self.V[y] else 0
            self.V[x] = (self.V[x] - self.V[y]) & 0xFF
        elif (opcode & 0xF00F) == 0x8006:
            self.V[0xF] = self.V[x] & 0x01
            self.V[x] >>= 1
        elif (opcode & 0xF00F) == 0x8007:
            self.V[0xF] = 1 if self.V[y] >= self.V[x] else 0
            self.V[x] = (self.V[y] - self.V[x]) & 0xFF
        elif (opcode & 0xF00F) == 0x800E:
            self.V[0xF] = (self.V[x] >> 7) & 0x01
            self.V[x] = (self.V[x] << 1) & 0xFF
        elif (opcode & 0xF00F) == 0x9000:
            if self.V[x] != self.V[y]:
                self.PC += 2
        elif (opcode & 0xF000) == 0xA000:
            self.I = nnn
        elif (opcode & 0xF000) == 0xB000:
            self.PC = nnn + self.V[0]
        elif (opcode & 0xF000) == 0xC000:
            self.V[x] = random.randint(0, 255) & nn
        elif (opcode & 0xF000) == 0xD000:
            self.V[0xF] = self.draw_sprite(x, y, n)
            self.update_display()
        elif (opcode & 0xF0FF) == 0xE09E:
            if self.keys[self.V[x]]:
                self.PC += 2
        elif (opcode & 0xF0FF) == 0xE0A1:
            if not self.keys[self.V[x]]:
                self.PC += 2
        elif (opcode & 0xF0FF) == 0xF007:
            self.V[x] = self.delay_timer
        elif (opcode & 0xF0FF) == 0xF00A:
            for i in range(16):
                if self.keys[i]:
                    self.V[x] = i
                    return
            self.PC -= 2
        elif (opcode & 0xF0FF) == 0xF015:
            self.delay_timer = self.V[x]
        elif (opcode & 0xF0FF) == 0xF018:
            self.sound_timer = self.V[x]
        elif (opcode & 0xF0FF) == 0xF01E:
            self.I = (self.I + self.V[x]) & 0xFFF
        elif (opcode & 0xF0FF) == 0xF029:
            self.I = 0x050 + (self.V[x] & 0xF) * 5
        elif (opcode & 0xF0FF) == 0xF033:
            self.memory[self.I] = self.V[x] // 100
            self.memory[self.I + 1] = (self.V[x] // 10) % 10
            self.memory[self.I + 2] = self.V[x] % 10
        elif (opcode & 0xF0FF) == 0xF055:
            for i in range(x + 1):
                self.memory[self.I + i] = self.V[i]
        elif (opcode & 0xF0FF) == 0xF065:
            for i in range(x + 1):
                self.V[i] = self.memory[self.I + i]
        else:
            print(f"Unknown opcode: {hex(opcode)} at PC={hex(self.PC-2)}")

    def update_timers(self) -> None:
        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1
            if self.sound_timer == 0:
                print("Beep motherfuckers!")

    def run(self, rom_path: str) -> None:
        self.load_rom(rom_path)
        last_timer_update = time.time()
        while True:
            self.handle_input()
            for _ in range(self.cycles_per_frame):
                self.emulate_cycle()
            if time.time() - last_timer_update >= 1/60:
                self.update_timers()
                last_timer_update = time.time()
            self.clock.tick(60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shitty chip-8 emulator ;)")
    parser.add_argument("rom", type=str, help="Path to ROM file")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--cycles", type=int, default=10, help="CPU cycles per frame (default: 10)")
    return parser.parse_args()


if __name__ == "__main__":
    args: argparse.Namespace = parse_args()
    emulator: Chip8 = Chip8(debug=args.debug, cycles_per_frame=args.cycles)
    emulator.run(args.rom)
