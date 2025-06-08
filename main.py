import argparse
import pygame
import random
import sys
import time
from enum import IntEnum
from pygame import Surface, font


class Opcodes(IntEnum):
    CLS = 0x00E0
    RET = 0x00EE
    JP_ADDR = 0x1000
    CALL_ADDR = 0x2000
    SE_VX_BYTE = 0x3000
    SNE_VX_BYTE = 0x4000
    SE_VX_VY = 0x5000
    LD_VX_BYTE = 0x6000
    ADD_VX_BYTE = 0x7000
    LD_VX_VY = 0x8000
    OR_VX_VY = 0x8001
    AND_VX_VY = 0x8002
    XOR_VX_VY = 0x8003
    ADD_VX_VY = 0x8004
    SUB_VX_VY = 0x8005
    SHR_VX = 0x8006
    SUBN_VX_VY = 0x8007
    SHL_VX = 0x800E
    SNE_VX_VY = 0x9000
    LD_I_ADDR = 0xA000
    JP_V0_ADDR = 0xB000
    RND_VX_BYTE = 0xC000
    DRW_VX_VY_NIBBLE = 0xD000
    SKP_VX = 0xE09E
    SKNP_VX = 0xE0A1
    LD_VX_DT = 0xF007
    LD_VX_K = 0xF00A
    LD_DT_VX = 0xF015
    LD_ST_VX = 0xF018
    ADD_I_VX = 0xF01E
    LD_F_VX = 0xF029
    LD_B_VX = 0xF033
    LD_I_VX = 0xF055
    LD_VX_I = 0xF065


class Constants:
    MEMORY_SIZE = 0x1000
    FONT_START_ADDR = 0x050
    PROGRAM_START_ADDR = 0x200
    REGISTER_COUNT = 16
    STACK_SIZE = 16
    DISPLAY_WIDTH = 64
    DISPLAY_HEIGHT = 32
    PIXEL_SIZE = 10
    SCREEN_WIDTH = DISPLAY_WIDTH * PIXEL_SIZE
    SCREEN_HEIGHT = DISPLAY_HEIGHT * PIXEL_SIZE
    DEBUG_PANEL_WIDTH = 200
    TIMER_FREQUENCY = 60
    SPRITE_WIDTH = 8
    VF_REGISTER = 0xF


class Chip8:
    def __init__(self, debug: bool = False, cycles_per_frame: int = 10) -> None:
        self.memory: list[int] = [0] * Constants.MEMORY_SIZE
        self.registers: list[int] = [0] * Constants.REGISTER_COUNT
        self.index_register: int = 0
        self.program_counter: int = Constants.PROGRAM_START_ADDR
        self.stack: list[int] = [0] * Constants.STACK_SIZE
        self.stack_pointer: int = 0
        self.delay_timer: int = 0
        self.sound_timer: int = 0
        self.display: list[list[int]] = [[0] * Constants.DISPLAY_WIDTH for _ in range(Constants.DISPLAY_HEIGHT)]
        
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

        self._load_fontset()
        
        self.keypad: list[int] = [0] * Constants.REGISTER_COUNT
        self.debug_mode: bool = debug
        self.cycles_per_frame: int = cycles_per_frame

        self._init_pygame()

    def _load_fontset(self) -> None:
        for index, font_byte in enumerate(self.fontset):
            self.memory[Constants.FONT_START_ADDR + index] = font_byte

    def _init_pygame(self) -> None:
        pygame.init()
        screen_width = Constants.SCREEN_WIDTH + (Constants.DEBUG_PANEL_WIDTH if self.debug_mode else 0)
        self.screen: Surface = pygame.display.set_mode((screen_width, Constants.SCREEN_HEIGHT))
        pygame.display.set_caption("Shitty chip-8 emulator")
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.debug_font: font.Font = pygame.font.SysFont("monospace", 14)

    def load_rom(self, rom_path: str) -> None:
        with open(rom_path, "rb") as file_handle:
            rom_data: bytes = file_handle.read()

        for index, byte_value in enumerate(rom_data):
            self.memory[Constants.PROGRAM_START_ADDR + index] = byte_value
        print(f"Loaded ROM: {rom_path}, size={len(rom_data)} bytes")

    def clear_display(self) -> None:
        self.display = [[0] * Constants.DISPLAY_WIDTH for _ in range(Constants.DISPLAY_HEIGHT)]

    def draw_sprite(self, reg_x: int, reg_y: int, sprite_height: int) -> int:
        collision_detected: int = 0
        start_x: int = self.registers[reg_x] & (Constants.DISPLAY_WIDTH - 1)
        start_y: int = self.registers[reg_y] & (Constants.DISPLAY_HEIGHT - 1)
        
        for row in range(sprite_height):
            sprite_byte: int = self.memory[self.index_register + row]
            for col in range(Constants.SPRITE_WIDTH):
                if sprite_byte & (0x80 >> col):
                    pixel_x: int = (start_x + col) & (Constants.DISPLAY_WIDTH - 1)
                    pixel_y: int = (start_y + row) & (Constants.DISPLAY_HEIGHT - 1)
                    if self.display[pixel_y][pixel_x] == 1:
                        collision_detected = 1
                    self.display[pixel_y][pixel_x] ^= 1
        return collision_detected

    def update_display(self) -> None:
        self.screen.fill((0, 0, 0))
        for row in range(Constants.DISPLAY_HEIGHT):
            for col in range(Constants.DISPLAY_WIDTH):
                if self.display[row][col]:
                    pygame.draw.rect(
                        self.screen, 
                        (255, 255, 255), 
                        (col * Constants.PIXEL_SIZE, row * Constants.PIXEL_SIZE, Constants.PIXEL_SIZE, Constants.PIXEL_SIZE)
                    )
    
        if self.debug_mode:
            self._draw_debug_panel()
        
        pygame.display.flip()

    def _draw_debug_panel(self) -> None:
        debug_x_offset = Constants.SCREEN_WIDTH
        pygame.draw.rect(self.screen, (50, 50, 50), (debug_x_offset, 0, Constants.DEBUG_PANEL_WIDTH, Constants.SCREEN_HEIGHT))
        
        debug_info: list[str] = [
            f"PC: {hex(self.program_counter)}",
            f"I:  {hex(self.index_register)}",
            f"SP: {self.stack_pointer}",
            "Registers:",
        ]
        
        for reg_group in range(0, Constants.REGISTER_COUNT, 4):
            register_line: str = " ".join(
                f"V{reg_index:X}={hex(self.registers[reg_index])[-2:].upper()}" 
                for reg_index in range(reg_group, min(reg_group + 4, Constants.REGISTER_COUNT))
            )
            debug_info.append(register_line)

        debug_info.append("Stack:")
        stack_values: str = " ".join(hex(self.stack[index])[-4:].upper() for index in range(self.stack_pointer))
        debug_info.append(stack_values if stack_values else "Empty")

        debug_info.append("Keys:")
        active_keys: str = " ".join(f"{index:X}" for index in range(Constants.REGISTER_COUNT) if self.keypad[index])
        debug_info.append(active_keys if active_keys else "None")

        for line_index, debug_line in enumerate(debug_info):
            text_surface: Surface = self.debug_font.render(debug_line, True, (255, 255, 255))
            self.screen.blit(text_surface, (debug_x_offset + 10, 10 + line_index * 18))

    def handle_input(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
                
        key_mapping: dict[int, int] = {
            pygame.K_1: 0x1, pygame.K_2: 0x2, pygame.K_3: 0x3, pygame.K_4: 0xC,
            pygame.K_q: 0x4, pygame.K_w: 0x5, pygame.K_e: 0x6, pygame.K_r: 0xD,
            pygame.K_a: 0x7, pygame.K_s: 0x8, pygame.K_d: 0x9, pygame.K_f: 0xE,
            pygame.K_z: 0xA, pygame.K_x: 0x0, pygame.K_c: 0xB, pygame.K_v: 0xF
        }
        
        pressed_keys: list[int] = pygame.key.get_pressed()

        for key_index in range(Constants.REGISTER_COUNT):
            self.keypad[key_index] = 0
            
        for pygame_key, chip8_key in key_mapping.items():
            if pressed_keys[pygame_key]:
                self.keypad[chip8_key] = 1

    def _extract_opcode_parts(self, opcode: int) -> tuple[int, int, int, int, int]:
        reg_x = (opcode & 0x0F00) >> 8
        reg_y = (opcode & 0x00F0) >> 4
        nibble = opcode & 0x000F
        byte_value = opcode & 0x00FF
        address = opcode & 0x0FFF
        return reg_x, reg_y, nibble, byte_value, address

    def _execute_arithmetic_ops(self, opcode: int, reg_x: int, reg_y: int) -> None:
        if (opcode & 0xF00F) == Opcodes.LD_VX_VY:
            self.registers[reg_x] = self.registers[reg_y]
        elif (opcode & 0xF00F) == Opcodes.OR_VX_VY:
            self.registers[reg_x] |= self.registers[reg_y]
        elif (opcode & 0xF00F) == Opcodes.AND_VX_VY:
            self.registers[reg_x] &= self.registers[reg_y]
        elif (opcode & 0xF00F) == Opcodes.XOR_VX_VY:
            self.registers[reg_x] ^= self.registers[reg_y]
        elif (opcode & 0xF00F) == Opcodes.ADD_VX_VY:
            result = self.registers[reg_x] + self.registers[reg_y]
            self.registers[Constants.VF_REGISTER] = 1 if result > 0xFF else 0
            self.registers[reg_x] = result & 0xFF
        elif (opcode & 0xF00F) == Opcodes.SUB_VX_VY:
            self.registers[Constants.VF_REGISTER] = 1 if self.registers[reg_x] >= self.registers[reg_y] else 0
            self.registers[reg_x] = (self.registers[reg_x] - self.registers[reg_y]) & 0xFF
        elif (opcode & 0xF00F) == Opcodes.SHR_VX:
            self.registers[Constants.VF_REGISTER] = self.registers[reg_x] & 0x01
            self.registers[reg_x] >>= 1
        elif (opcode & 0xF00F) == Opcodes.SUBN_VX_VY:
            self.registers[Constants.VF_REGISTER] = 1 if self.registers[reg_y] >= self.registers[reg_x] else 0
            self.registers[reg_x] = (self.registers[reg_y] - self.registers[reg_x]) & 0xFF
        elif (opcode & 0xF00F) == Opcodes.SHL_VX:
            self.registers[Constants.VF_REGISTER] = (self.registers[reg_x] >> 7) & 0x01
            self.registers[reg_x] = (self.registers[reg_x] << 1) & 0xFF

    def _execute_fx_ops(self, opcode: int, reg_x: int) -> None:
        if (opcode & 0xF0FF) == Opcodes.LD_VX_DT:
            self.registers[reg_x] = self.delay_timer
        elif (opcode & 0xF0FF) == Opcodes.LD_VX_K:
            for key_index in range(Constants.REGISTER_COUNT):
                if self.keypad[key_index]:
                    self.registers[reg_x] = key_index
                    return
            self.program_counter -= 2
        elif (opcode & 0xF0FF) == Opcodes.LD_DT_VX:
            self.delay_timer = self.registers[reg_x]
        elif (opcode & 0xF0FF) == Opcodes.LD_ST_VX:
            self.sound_timer = self.registers[reg_x]
        elif (opcode & 0xF0FF) == Opcodes.ADD_I_VX:
            self.index_register = (self.index_register + self.registers[reg_x]) & 0xFFF
        elif (opcode & 0xF0FF) == Opcodes.LD_F_VX:
            self.index_register = Constants.FONT_START_ADDR + (self.registers[reg_x] & 0xF) * 5
        elif (opcode & 0xF0FF) == Opcodes.LD_B_VX:
            self.memory[self.index_register] = self.registers[reg_x] // 100
            self.memory[self.index_register + 1] = (self.registers[reg_x] // 10) % 10
            self.memory[self.index_register + 2] = self.registers[reg_x] % 10
        elif (opcode & 0xF0FF) == Opcodes.LD_I_VX:
            for reg_index in range(reg_x + 1):
                self.memory[self.index_register + reg_index] = self.registers[reg_index]
        elif (opcode & 0xF0FF) == Opcodes.LD_VX_I:
            for reg_index in range(reg_x + 1):
                self.registers[reg_index] = self.memory[self.index_register + reg_index]

    def emulate_cycle(self) -> None:
        opcode: int = (self.memory[self.program_counter] << 8) | self.memory[self.program_counter + 1]
        self.program_counter += 2
        
        reg_x, reg_y, nibble, byte_value, address = self._extract_opcode_parts(opcode)

        # alright, let's execute this shit
        if opcode == Opcodes.CLS:
            self.clear_display()
        elif opcode == Opcodes.RET:
            self.stack_pointer -= 1
            self.program_counter = self.stack[self.stack_pointer]
        elif (opcode & 0xF000) == Opcodes.JP_ADDR:
            self.program_counter = address
        elif (opcode & 0xF000) == Opcodes.CALL_ADDR:
            self.stack[self.stack_pointer] = self.program_counter
            self.stack_pointer += 1
            self.program_counter = address
        elif (opcode & 0xF000) == Opcodes.SE_VX_BYTE:
            if self.registers[reg_x] == byte_value:
                self.program_counter += 2
        elif (opcode & 0xF000) == Opcodes.SNE_VX_BYTE:
            if self.registers[reg_x] != byte_value:
                self.program_counter += 2
        elif (opcode & 0xF000) == Opcodes.SE_VX_VY and (opcode & 0x000F) == 0:
            if self.registers[reg_x] == self.registers[reg_y]:
                self.program_counter += 2
        elif (opcode & 0xF000) == Opcodes.LD_VX_BYTE:
            self.registers[reg_x] = byte_value
        elif (opcode & 0xF000) == Opcodes.ADD_VX_BYTE:
            self.registers[reg_x] = (self.registers[reg_x] + byte_value) & 0xFF
        elif (opcode & 0xF000) == 0x8000:
            self._execute_arithmetic_ops(opcode, reg_x, reg_y)
        elif (opcode & 0xF00F) == Opcodes.SNE_VX_VY:
            if self.registers[reg_x] != self.registers[reg_y]:
                self.program_counter += 2
        elif (opcode & 0xF000) == Opcodes.LD_I_ADDR:
            self.index_register = address
        elif (opcode & 0xF000) == Opcodes.JP_V0_ADDR:
            self.program_counter = address + self.registers[0]
        elif (opcode & 0xF000) == Opcodes.RND_VX_BYTE:
            self.registers[reg_x] = random.randint(0, 255) & byte_value
        elif (opcode & 0xF000) == Opcodes.DRW_VX_VY_NIBBLE:
            self.registers[Constants.VF_REGISTER] = self.draw_sprite(reg_x, reg_y, nibble)
            self.update_display()
        elif (opcode & 0xF0FF) == Opcodes.SKP_VX:
            if self.keypad[self.registers[reg_x]]:
                self.program_counter += 2
        elif (opcode & 0xF0FF) == Opcodes.SKNP_VX:
            if not self.keypad[self.registers[reg_x]]:
                self.program_counter += 2
        elif (opcode & 0xF000) == 0xF000:
            self._execute_fx_ops(opcode, reg_x)
        else:
            print(f"Unknown opcode: {hex(opcode)} at PC={hex(self.program_counter-2)}")

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
                
            if time.time() - last_timer_update >= 1/Constants.TIMER_FREQUENCY:
                self.update_timers()
                last_timer_update = time.time()
                
            self.clock.tick(Constants.TIMER_FREQUENCY)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shitty chip-8 emulator ;)")
    parser.add_argument("rom", type=str, help="Path to ROM file")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    parser.add_argument("--cycles", type=int, default=10, help="CPU cycles per frame (default: 10)")
    return parser.parse_args()


if __name__ == "__main__":
    arguments: argparse.Namespace = parse_arguments()
    emulator: Chip8 = Chip8(debug=arguments.debug, cycles_per_frame=arguments.cycles)
    emulator.run(arguments.rom)
