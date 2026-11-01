// Category: Pointer Errors
// Error: Dereferencing nullptr after null check

#include <iostream>

void process(int* ptr) {
    if (ptr == nullptr) {
        *ptr = 0;  // ERROR: Dereferencing null pointer inside null check
    }
}

int main() {
    int* ptr = nullptr;
    process(ptr);
    
    return 0;
}
