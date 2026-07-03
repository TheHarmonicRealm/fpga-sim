#include <unordered_map>
#include <variant>
#include <string>
#include <iostream>
#include "verilated.h"
#include "port_ref.h"

QData make_mask(int width) {
    QData mask = 0;
    for(int i = 0; i < width; i++) {
        mask <<= 1;
        mask |= 1;
    }
    return mask;
}


PortReference::PortReference(void* data, unsigned int width) {
    if(width > 64) {
        std::cout << "Port of width" << width << "is too big!!";
        exit(1);
    }

    this->width = width;
    this->internal_pointer = data;
    this->mask = make_mask(width);
}
void PortReference::set(QData value) {
    if(this->width <= 8) { // CData
        // *(CData*) this->internal_pointer = value & this->mask;
        *(CData*) this->internal_pointer = value & this->mask;
    }
    else if(this->width <= 16) { // SData
        *(SData*) this->internal_pointer = value & this->mask;
    }
    else if(this->width <= 32) { // IData
        *(IData*) this->internal_pointer = value & this->mask;
    }
    else if(this->width <= 64) { // QData
        *(QData*) this->internal_pointer = value & this->mask;
    }
    else {
        std::cout << "width is " << this->width << std::endl;
    }
}

QData PortReference::get() {
    if(this->width <= 8) { // CData
        return *(CData*) this->internal_pointer & this->mask;
    }
    else if(this->width <= 16) { // SData
        return *(SData*) this->internal_pointer & this->mask;
    }
    else if(this->width <= 32) { // IData
        return *(IData*) this->internal_pointer & this->mask;
    }
    else if(this->width <= 64) { // QData
        return *(QData*) this->internal_pointer & this->mask;
    }
    else {
        // (should be unreachable)
        std::cout << "Width is too high: " << this->width << std::endl;
        return {};
    }
}